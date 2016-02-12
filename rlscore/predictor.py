
from scipy import sparse as sp
import numpy as np

from rlscore.utilities import array_tools

class PredictorInterface(object):
    """Predictor interface
    
    Attributes
    ----------
    predictor: predictor object
        predicts outputs for new instance
    """
    

    
    def predict(self, X):
        """Predicts outputs for new inputs
    
        Parameters
         ----------
        X: {array-like, sparse matrix}, shape = [n_samples, n_features]
           input data matrix
            
        Returns
        -------
        P: array, shape = [n_samples, n_tasks]
            predictions
        """
        return self.predictor.predict(X)

class KernelPredictor(object):
    """Represents a dual model for making predictions.
    
    New predictions are made by computing K*A, where K is the
    kernel matrix between test and training examples, and A contains
    the dual coefficients.

    Parameters
    ----------
    A: array-like, shape = [n_samples] or [n_samples, n_labels]
        dual coefficients
    kernel : kernel object
        kernel object, initialized with the basis vectors and kernel parameters
        
    Attributes
    ----------
    A: array-like, shape = [n_samples] or [n_samples, n_labels]
        dual coefficients
    kernel: kernel object
        kernel object, initialized with the basis vectors and kernel parameters
    """
    
    def __init__(self, A, kernel):
        self.kernel = kernel
        self.A = A
        self.A = np.squeeze(array_tools.as_array(self.A))
    
    
    def predict(self, X):
        """Computes predictions for test examples.

        Parameters
        ----------
        X: {array-like, sparse matrix}, shape = [n_samples, n_features]
            test data matrix
        
        Returns
        ----------
        P: array, shape = [n_samples] or [n_samples, n_labels]
            predictions
        """
        K = self.kernel.getKM(X)
        if len(X.shape) < 2: #Cheap hack!
            K = np.squeeze(K)
        P = np.dot(K, self.A)
        return P


class LinearPredictor(object):
    """Represents a linear model for making predictions.
    
    New predictions are made by computing X*W+b.

    Parameters
    ----------
    W: array-like, shape = [n_features] or [n_features, n_labels]
        primal coefficients
    b : float or array-like with shape = [n_labels]
        bias term(s)

    Attributes
    ----------
    W: array-like, shape = [n_features] or [n_features, n_labels]
        primal coefficients
    b: float or array-like with shape = [n_labels]
        bias term(s)
    """
    
    def __init__(self, W, b = 0.):
        self.W = np.squeeze(array_tools.as_array(W))
        if self.W.ndim == 0:
            self.W = self.W.reshape(1)
        self.b = np.squeeze(np.array(b))
    
    
    def predict(self, X):
        """Computes predictions for test examples.

        Parameters
        ----------
        X: {array-like, sparse matrix}, shape = [n_samples, n_features]
            test data matrix
        
        Returns
        ----------
        P: array, shape = [n_samples, n_labels]
            predictions
        """
        W = self.W
        assert len(X.shape) < 3
        if sp.issparse(X):
            P = X * W
        elif isinstance(X, np.matrix):
            P = np.dot(np.array(X), W)
        else:
            P = np.dot(X, W)
        P = P + self.b
        #P = array_tools.as_array(P)
        return P



