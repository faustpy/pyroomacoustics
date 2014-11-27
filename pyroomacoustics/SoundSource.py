
import numpy as np
import constants


class SoundSource(object):
    '''
    A class to represent sound sources
    '''

    def __init__(
            self,
            position,
            images=None,
            damping=None,
            generators=None,
            walls=None,
            orders=None,
            signal=None,
            delay=0):
        '''
        This object represent a sound source in a room by a list containing the original source position
        as well as all the image sources, up to some maximum order.

        It also keeps track of the sequence of generated images and the index of the walls (in the original room)
        that generated the reflection.
        '''

        self.position = np.array(position)
        self.dim = self.position.shape[0]

        if (images is None):
            # set to empty list if nothing provided
            self.images = np.array([position]).T
            self.damping = np.array([1.])
            self.generators = np.array([np.nan])
            self.walls = np.array([np.nan])
            self.orders = np.array([0])

        else:
            # we need to have damping factors for every image
            if (damping is None):
                # set to one if not set
                damping = np.ones(images.shape[1])

            if images.shape[1] is not damping.shape[0]:
                raise NameError('Images and damping must have same shape')

            if generators is not None and generators.shape[0] is not images.shape[1]:
                raise NameError('Images and generators must have same shape')

            if walls is not None and walls.shape[0] is not images.shape[1]:
                raise NameError('Images and walls must have same shape')

            if orders is not None and orders.shape[0] is not images.shape[1]:
                raise NameError('Images and orders must have same shape')


            self.images = images
            self.damping = damping
            self.walls = walls
            self.generators = generators
            self.orders = orders

        # store the natural ordering for the images
        self.I = np.arange(self.images.shape[1])

        # The sound signal of the source
        self.signal = signal
        self.delay = delay

    def addSignal(signal):

        self.signal = signal

    def distance(self, ref_point):

        return np.sqrt(np.sum((self.images - ref_point[:,np.newaxis])**2, axis=0))

    def setOrdering(self, ordering='nearest', ref_point=None):

        if ordering is 'nearest':

            if ref_point is None:
                raise NameError('For nearest ordering, a reference point is needed.')

            self.I = self.distance(ref_point).argsort()

        elif ordering is 'strongest':

            if ref_point is None:
                raise NameError('For strongest ordering, a reference point is needed.')

            strength = self.damping/(4*np.pi*self.distance(ref_point))
            self.I = strength.argsort()

        elif ordering is 'order':

            if max_order is None:
                max_order = self.max_order

            self.I = (np.orders <= max_order)

        else:
            raise NameError('Ordering can be nearest, strongest, order.')


    def __getitem__(self, index):
        '''
        Overload the bracket operator to access a subset image sources
        '''

        if isinstance(index, slice) or isinstance(index, init):
            s = SoundSource(
                    self.position,
                    images=self.images[:,self.I[index]],
                    damping=self.damping[self.I[index]],
                    orders=self.orders[self.I[index]],
                    signal=self.signal,
                    delay=self.delay)
        else:
            s = SoundSource(
                    self.position,
                    images=self.images[:,index],
                    damping=self.damping[index],
                    orders=self.orders[index],
                    signal=self.signal,
                    delay=self.delay)

        return s


    def getImages(self, max_order=None, max_distance=None, n_nearest=None, ref_point=None):
        '''
        Keep this for compatibility
        Now replaced by the bracket operator and the setOrdering function.
        '''

        # TO DO: Add also n_strongest

        # TO DO: Make some of these thing exclusive (e.g. can't have n_nearest
        # AND n_strongest (although could have max_order AND n_nearest)

        # TO DO: Make this more efficient if bottleneck (unlikely)

        if (max_order is None):
            max_order = np.max(self.orders)

        # stack source and all images
        I_ord = (self.orders <= max_order)
        img = self.images[:,I_ord]

        if (n_nearest is not None):
            dist = np.sum((img - ref_point)**2, axis=0)
            I_near = dist.argsort()[0:n_nearest]
            img = img[:,I_near]

        return img


    def getDamping(self, max_order=None):
        if (max_order is None):
            max_order = len(np.max(self.orders))

        return self.damping[self.orders <= max_order]


    def getRIR(self, mic, Fs, t0=0., t_max=None, c=constants.c):
        '''
        Compute the room impulse response between the source
        and the microphone whose position is given as an
        argument.
        '''


        # compute the distance
        dist = self.distance(mic)
        time = dist / c + t0
        alpha = self.damping/(4.*np.pi*dist)

        # the number of samples needed
        if t_max is None:
            N = np.ceil(t_max * Fs)
        else:
            N = np.ceil((t_max - t0)*Fs)

        t = np.arange(N)/float(Fs)
        ir = np.zeros(t.shape)

        #from utilities import lowPassDirac
        import utilities as u

        return u.lowPassDirac(time[:,np.newaxis], alpha[:,np.newaxis], Fs, N).sum(axis=0)


def buildRIRMatrix(mics, sources, Lg, Fs, epsilon=5e-3, unit_damping=False):
    '''
    A function to build the channel matrix for many sources and microphones

    mics is a dim-by-M ndarray where each column is the position of a microphone
    sources is a list of SoundSource objects
    Lg is the length of the beamforming filters
    Fs is the sampling frequency
    epsilon determines how long the sinc is let to decay. Defaults to epsilon=5e-3
    unit_damping determines if the wall damping parameters are used or not. Default to false.

    returns the RIR matrix H = 

    --------------------
    | H_{11} H_{12} ...
    | ...
    |
    --------------------

    where H_{ij} is channel matrix between microphone i and source j.
    H is of type (M*Lg)x((Lg+Lh-1)*S) where Lh is the channel length (determined by epsilon),
    and M, S are the number of microphones, sources, respectively.
    '''

    from beamforming import distance
    from utilities import lowPassDirac
    from scipy.linalg import toeplitz

    # set the boundaries of RIR filter for given epsilon
    d_min = np.inf
    d_max = 0.
    dmp_max = 0.
    for s in xrange(len(sources)):
        dist_mat = distance(mics, sources[s].images)
        if unit_damping is True:
            dmp_max = np.maximum((1./(4*np.pi*dist_mat)).max(), dmp_max)
        else:
            dmp_max = np.maximum((sources[s].damping[np.newaxis,:]/(4*np.pi*dist_mat)).max(), dmp_max)
        d_min = np.minimum(dist_mat.min(), d_min)
        d_max = np.maximum(dist_mat.max(), d_max)
    t_max = d_max/constants.c
    t_min = d_min/constants.c
        
    offset = dmp_max/(np.pi*Fs*epsilon)

    # RIR length
    Lh = int((t_max - t_min + 2*offset)*float(Fs))

    # build the channel matrix
    L = Lg + Lh - 1
    H = np.zeros((Lg*mics.shape[1], len(sources)*L))

    for s in xrange(len(sources)):
        for r in np.arange(mics.shape[1]):

            dist = sources[s].distance(mics[:,r])
            time = dist/constants.c - t_min + offset
            if unit_damping is True:
                dmp = 1./(4*np.pi*dist)
            else:
                dmp = sources[s].damping/(4*np.pi*dist)

            hs = lowPassDirac(time[:,np.newaxis], dmp[:,np.newaxis], Fs, Lh).sum(axis=0)
            row = np.pad(hs, ((0,L-len(hs))), mode='constant')
            col = np.pad(hs[:1], ((0, Lg-1)), mode='constant')
            H[r*Lg:(r+1)*Lg,s*L:(s+1)*L] = toeplitz(col, row)

    return H
