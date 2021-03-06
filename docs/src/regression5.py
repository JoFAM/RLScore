import numpy as np
from rlscore.learner import LeaveOneOutRLS
from rlscore.measure import sqerror

from housing_data import load_housing


def train_rls():
    #Selects both the gamma parameter for Gaussian kernel, and regparam with loocv
    X_train, Y_train, X_test, Y_test = load_housing()
    regparams = [2.**i for i in range(-15, 16)]
    gammas = regparams
    best_regparam = None
    best_gamma = None
    best_error = float("inf")
    best_learner = None
    for gamma in gammas:
        #New RLS is initialized for each kernel parameter
        learner = LeaveOneOutRLS(X_train, Y_train, kernel="GaussianKernel", gamma=gamma, regparams=regparams)
        e = np.min(learner.cv_performances)
        if e < best_error:
            best_error = e
            best_regparam = learner.regparam
            best_gamma = gamma
            best_learner = learner
    P_test = best_learner.predict(X_test)
    print("best parameters gamma %f regparam %f" %(best_gamma, best_regparam))
    print("best leave-one-out error %f" %best_error)
    print("test error %f" %sqerror(Y_test, P_test))

if __name__=="__main__":
    train_rls()
