
import numpy as np
import scipy.sparse

from rlscore.utilities import decomposition
from rlscore.utilities import array_tools
from rlscore.utilities import creators
from rlscore.measure.measure_utilities import UndefinedPerformance
from rlscore.predictor import PredictorInterface
from rlscore.measure import cindex
from rlscore.utilities.cross_validation import grid_search
from rlscore.measure.measure_utilities import qids_to_splits

class QueryRankRLS(PredictorInterface):
    """RankRLS algorithm for learning to rank
    
    Implements the learning algorithm for learning from query-structured
    data. 

    Parameters
    ----------
    X: {array-like, sparse matrix}, shape = [n_samples, n_features]
        Data matrix
    Y: {array-like}, shape = [n_samples] or [n_samples, n_labels]
        Training set labels
    qids: list of query ids, shape = [n_samples]
        Training set qids
    regparam: float, optional
        regularization parameter, regparam > 0 (default=1.0)
    kernel: {'LinearKernel', 'GaussianKernel', 'PolynomialKernel', 'PrecomputedKernel', ...}
        kernel function name, imported dynamically from rlscore.kernel
    basis_vectors: {array-like, sparse matrix}, shape = [n_bvectors, n_features], optional
        basis vectors (typically a randomly chosen subset of the training data)

    Other Parameters
    ----------------
    Typical kernel parameters include:
    bias: float, optional
        LinearKernel: the model is w*x + bias*w0, (default=1.0)
    gamma: float, optional
        GaussianKernel: k(xi,xj) = e^(-gamma*<xi-xj,xi-xj>) (default=1.0)
        PolynomialKernel: k(xi,xj) = (gamma * <xi, xj> + coef0)**degree (default=1.0)     
    coef0: float, optional
        PolynomialKernel: k(xi,xj) = (gamma * <xi, xj> + coef0)**degree (default=0.)
    degree: int, optional
        PolynomialKernel: k(xi,xj) = (gamma * <xi, xj> + coef0)**degree (default=2)
        
    Attributes
    -----------
    predictor: {LinearPredictor, KernelPredictor}
        trained predictor
        
    Notes
    -----

    Computational complexity of training:
    m = n_samples, d = n_features, l = n_labels, b = n_bvectors
    
    O(m^3 + lm^2): basic case
    
    O(md^2 + lmd): Linear Kernel, d < m
    
    O(mb^2 +lmb): Sparse approximation with basis vectors 

    RankRLS algorithm was first introduced in [1], extended version of the work and the
    efficient  leave-query-out cross-validation method implemented in
    the method 'holdout' are found in [2].
        
    References
    ----------

    [1] Tapio Pahikkala, Evgeni Tsivtsivadze, Antti Airola, Jorma Boberg and Tapio Salakoski
    Learning to rank with pairwise regularized least-squares.
    In Thorsten Joachims, Hang Li, Tie-Yan Liu, and ChengXiang Zhai, editors,
    SIGIR 2007 Workshop on Learning to Rank for Information Retrieval, pages 27--33, 2007.
    
    [2] Tapio Pahikkala, Evgeni Tsivtsivadze, Antti Airola, Jouni Jarvinen, and Jorma Boberg.
    An efficient algorithm for learning to rank from preference graphs.
    Machine Learning, 75(1):129-165, 2009.
    """


    def __init__(self, X, Y, qids, regparam = 1.0, kernel='LinearKernel', basis_vectors = None, **kwargs):
        kwargs["bias"] = 0.
        kwargs['kernel'] =  kernel
        kwargs['X'] = X
        if basis_vectors != None:
            kwargs['basis_vectors'] = basis_vectors
        self.svdad = creators.createSVDAdapter(**kwargs)
        self.Y = np.mat(array_tools.as_2d_array(Y))
        self.regparam = regparam
        self.svals = self.svdad.svals
        self.svecs = self.svdad.rsvecs
        self.size = self.Y.shape[0]
        self.size = self.Y.shape[0]
        self.qids = map_qids(qids)
        self.qidlist = qids_to_splits(self.qids)
        self.solve(self.regparam)
    
    
    def solve(self, regparam=1.0):
        """Trains the learning algorithm, using the given regularization parameter.
               
        Parameters
        ----------
        regparam: float (regparam > 0)
            regularization parameter
        """
        if not hasattr(self, "D"):
            qidlist = self.qids
            objcount = max(qidlist) + 1
            
            labelcounts = np.mat(np.zeros((1, objcount)))
            Pvals = np.ones(self.size)
            for i in range(self.size):
                qid = qidlist[i]
                labelcounts[0, qid] = labelcounts[0, qid] + 1
            D = np.mat(np.ones((1, self.size), dtype=np.float64))
            
            #The centering matrix way (HO computations should be modified accordingly too)
            for i in range(self.size):
                qid = qidlist[i]
                Pvals[i] = 1. / np.sqrt(labelcounts[0, qid])
            
            #The old Laplacian matrix way
            #for i in range(self.size):
            #    qid = qidlist[i]
            #    D[0, i] = labelcounts[0, qid]
            
            P = scipy.sparse.coo_matrix((Pvals, (np.arange(0, self.size), qidlist)), shape=(self.size,objcount))
            P_csc = P.tocsc()
            P_csr = P.tocsr()
            
            
            #Eigenvalues of the kernel matrix
            #evals = np.multiply(self.svals, self.svals)
            
            #Temporary variables
            ssvecs = np.multiply(self.svecs, self.svals)
            
            #These are cached for later use in solve and holdout functions
            ssvecsTLssvecs = (np.multiply(ssvecs.T, D) - (ssvecs.T * P_csc) * P_csr.T) * ssvecs
            LRsvals, LRevecs = decomposition.decomposeKernelMatrix(ssvecsTLssvecs)
            LRevals = np.multiply(LRsvals, LRsvals)
            LY = np.multiply(D.T, self.Y) - P_csr * (P_csc.T * self.Y)
            self.multipleright = LRevecs.T * (ssvecs.T * LY)
            self.multipleleft = ssvecs * LRevecs
            self.LRevals = LRevals
            self.LRevecs = LRevecs
            self.D = D
        
        
        self.regparam = regparam
        
        #Compute the eigenvalues determined by the given regularization parameter
        self.neweigvals = 1. / (self.LRevals + regparam)
        self.A = self.svecs * np.multiply(1. / self.svals.T, (self.LRevecs * np.multiply(self.neweigvals.T, self.multipleright)))
        #if self.U == None:
            #Dual RLS
        #    pass
            #self.A = self.svecs * np.multiply(1. / self.svals.T, (self.LRevecs * np.multiply(self.neweigvals.T, self.multipleright)))
        #else:
            #Primal RLS
            #self.A = self.U.T * (self.LRevecs * np.multiply(self.neweigvals.T, self.multipleright))
            #self.A = self.U.T * np.multiply(self.svals.T,  self.svecs.T * self.A)
        #self.results['model'] = self.getModel()
        self.predictor = self.svdad.createModel(self)
    
    
    def holdout(self, indices):
        """Computes hold-out predictions for a trained RLS.
        
        Parameters
        ----------
        indices: list of indices, shape = [n_hsamples]
            list of indices of training examples belonging to the set for which the
            hold-out predictions are calculated. Should correspond to one query.

        Returns
        -------
        F : array, shape = [n_hsamples, n_labels]
            holdout query predictions
        """
        indices = array_tools.as_index_list(indices, self.Y.shape[0])
        if len(indices) == 0:
            raise IndexError('Hold-out predictions can not be computed for an empty hold-out set.')   
        if len(indices) != len(np.unique(indices)):
            raise IndexError('Hold-out can have each index only once.')        
        hoqid = self.qids[indices[0]]
        for ind in indices:
            if not hoqid == self.qids[ind]:
                raise IndexError('All examples in the hold-out set must have the same qid.')
        
        indlen = len(indices)
        Qleft = self.multipleleft[indices]
        sqrtQho = np.multiply(Qleft, np.sqrt(self.neweigvals))
        Qho = sqrtQho * sqrtQho.T
        #Qho = Qleft * np.multiply(self.neweigvals.T, Qleft.T)
        Pho = np.mat(np.ones((len(indices),1))) / np.sqrt(len(indices))
        Yho = self.Y[indices]
        Dho = self.D[:, indices]
        LhoYho = np.multiply(Dho.T, Yho) - Pho * (Pho.T * Yho)
        RQY = Qleft * np.multiply(self.neweigvals.T, self.multipleright) - Qho * LhoYho
        #RQRTLho = np.multiply(Qho, Dho) - (Qho * Pho) * Pho.T
        #print Dho.shape, sqrtQho.shape, Pho.shape
        sqrtRQRTLho = np.multiply(Dho.T, sqrtQho) - Pho * (Pho.T * sqrtQho)
        if sqrtQho.shape[0] <= sqrtQho.shape[1]:
            RQRTLho = sqrtQho * sqrtRQRTLho.T
            I = np.mat(np.identity(indlen))
            return np.squeeze(np.array((I - RQRTLho).I * RQY))
        else:
            RQRTLho = sqrtRQRTLho.T * sqrtQho
            I = np.mat(np.identity(sqrtQho.shape[1]))
            return np.squeeze(np.array(RQY + sqrtQho * ((I - RQRTLho).I * (sqrtRQRTLho.T * RQY))))
        #return RQY - RQRTLho * la.inv(-I + RQRTLho) * RQY

class LeaveQueryOutRankRLS(PredictorInterface):

    """RankRLS algorithm for learning to rank with query-structured data. Selects
    automatically regularization parameter using leave-query-out cross-validation.

    Parameters
    ----------
    X: {array-like, sparse matrix}, shape = [n_samples, n_features]
        Data matrix
    Y: {array-like}, shape = [n_samples] or [n_samples, n_labels]
        Training set labels
    qids: list of query ids, shape = [n_samples]
        Training set qids
    regparam: float, optional
        regularization parameter, regparam > 0 (default=1.0)
    kernel: {'LinearKernel', 'GaussianKernel', 'PolynomialKernel', 'PrecomputedKernel', ...}
        kernel function name, imported dynamically from rlscore.kernel
    basis_vectors: {array-like, sparse matrix}, shape = [n_bvectors, n_features], optional
        basis vectors (typically a randomly chosen subset of the training data)

    Other Parameters
    ----------------
    Typical kernel parameters include:
    bias: float, optional
        LinearKernel: the model is w*x + bias*w0, (default=1.0)
    gamma: float, optional
        GaussianKernel: k(xi,xj) = e^(-gamma*<xi-xj,xi-xj>) (default=1.0)
        PolynomialKernel: k(xi,xj) = (gamma * <xi, xj> + coef0)**degree (default=1.0)       
    coef0: float, optional
        PolynomialKernel: k(xi,xj) = (gamma * <xi, xj> + coef0)**degree (default=0.)
    degree: int, optional
        PolynomialKernel: k(xi,xj) = (gamma * <xi, xj> + coef0)**degree (default=2)
        
    Attributes
    -----------
    predictor: {LinearPredictor, KernelPredictor}
        trained predictor
    cv_performances: array, shape = [grid_size]
        leave-query-out performances for each grid point
    cv_predictions: list of 1D  or 2D arrays, shape = [grid_size, n_queries]
        predictions for each query, shapes [query_size] or [query_size, n_labels]
    regparam: float
        regparam from grid with best performance
        
    Notes
    -----

    Computational complexity of training:
    m = n_samples, d = n_features, l = n_labels, b = n_bvectors
    
    O(m^3 + lm^2): basic case
    
    O(md^2 + lmd): Linear Kernel, d < m
    
    O(mb^2 +lmb): Sparse approximation with basis vectors 
        
    RankRLS algorithm was first introduced in [1], extended version of the work and the
    efficient  leave-query-out cross-validation method implemented in
    the method 'holdout' are found in [2].
        
    References
    ----------

    [1] Tapio Pahikkala, Evgeni Tsivtsivadze, Antti Airola, Jorma Boberg and Tapio Salakoski
    Learning to rank with pairwise regularized least-squares.
    In Thorsten Joachims, Hang Li, Tie-Yan Liu, and ChengXiang Zhai, editors,
    SIGIR 2007 Workshop on Learning to Rank for Information Retrieval, pages 27--33, 2007.
    
    [2] Tapio Pahikkala, Evgeni Tsivtsivadze, Antti Airola, Jouni Jarvinen, and Jorma Boberg.
    An efficient algorithm for learning to rank from preference graphs.
    Machine Learning, 75(1):129-165, 2009.
    """
   
    def __init__(self, X, Y, qids, kernel='LinearKernel', basis_vectors = None, regparams=None, measure=None, **kwargs):
        if regparams == None:
            grid = [2**x for x in range(-15, 15)]
        else:
            grid = regparams
        if measure == None:
            self.measure = cindex
        else:
            self.measure = measure
        learner = QueryRankRLS(X, Y, qids, grid[0], kernel, basis_vectors, **kwargs)
        crossvalidator = LQOCV(learner, measure)
        self.cv_performances, self.cv_predictions,  self.regparam = grid_search(crossvalidator, grid)
        self.predictor = learner.predictor

class LQOCV(object):
    
    def __init__(self, learner, measure):
        self.rls = learner
        self.measure = measure

    def cv(self, regparam):
        rls = self.rls
        measure = self.measure
        rls.solve(regparam)
        Y = rls.Y
        performances = []
        predictions = []
        folds = rls.qidlist
        for fold in folds:
            P = rls.holdout(fold)
            predictions.append(P)
            try:
                performance = measure(Y[fold], P)
                performances.append(performance)
            except UndefinedPerformance:
                pass
            #performance = measure_utilities.aggregate(performances)
        if len(performances) > 0:
            performance = np.mean(performances)
        else:
            raise UndefinedPerformance("Performance undefined for all folds")
        return performance, predictions
    
def map_qids(qids):
    qidmap = {}
    i = 0
    for qid in qids:
        if not qid in qidmap:
            qidmap[qid] = i
            i+=1
    new_qids = []
    for qid in qids:
        new_qids.append(qidmap[qid])
    return new_qids
