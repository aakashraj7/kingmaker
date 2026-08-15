from sklearn.linear_model import LogisticRegression, Perceptron, LinearRegression, BayesianRidge
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, BaggingClassifier, GradientBoostingClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
from sklearn.cluster import KMeans

# Catalog of algorithms with descriptions & inductive biases
CLASSIFIERS_METADATA = {
    "logistic_regression": {
        "name": "Logistic Regression",
        "type": "Supervised Learning (Classification)",
        "inductive_bias": "Assumes a linear decision boundary in the log-odds space of the features.",
        "description": "Models the probability of a discrete target outcome using a logistic function.",
        "default_params": {"C": 1.0, "max_iter": 1000}
    },
    "perceptron": {
        "name": "Perceptron Algorithm",
        "type": "Supervised Learning (Classification)",
        "inductive_bias": "Assumes classes are linearly separable. Learns a linear decision boundary sequentially.",
        "description": "The simplest type of feedforward neural network—a linear classifier.",
        "default_params": {"penalty": None, "max_iter": 1000, "eta0": 1.0}
    },
    "naive_bayes": {
        "name": "Naive Bayes Classifier",
        "type": "Supervised Learning (Classification)",
        "inductive_bias": "Assumes absolute conditional independence between every pair of features given the class label.",
        "description": "Probabilistic classifier based on applying Bayes' theorem with strong independence assumptions.",
        "default_params": {}
    },
    "svm": {
        "name": "Support Vector Machine (SVM)",
        "type": "Supervised Learning (Classification)",
        "inductive_bias": "Assumes a maximum-margin separator is optimal. Uses kernel trick to project to higher dimensions.",
        "description": "Finds a hyperplane in an N-dimensional space that distinctly classifies data points.",
        "default_params": {"C": 1.0, "kernel": "rbf"}
    },
    "decision_tree": {
        "name": "Decision Tree",
        "type": "Supervised Learning (Classification)",
        "inductive_bias": "Prefers shorter trees over longer trees. Orthogonal splits that minimize impurity (Gini/Entropy).",
        "description": "A tree-structured classifier where internal nodes represent features, branches represent rules, and leaves represent outcomes.",
        "default_params": {"max_depth": 5, "min_samples_split": 2}
    },
    "random_forest": {
        "name": "Random Forest",
        "type": "Supervised Ensemble (Bagging)",
        "inductive_bias": "Reduces variance of individual decision trees by averaging their independent predictions.",
        "description": "An ensemble of decision trees trained on bootstrap samples with random feature subsets.",
        "default_params": {"n_estimators": 50, "max_depth": 5}
    },
    "knn": {
        "name": "K-Nearest Neighbour (KNN)",
        "type": "Supervised Learning (Classification)",
        "inductive_bias": "Assumes smooth decision boundaries; points close to each other in feature space share the same label.",
        "description": "Instance-based, non-parametric classifier that votes based on the 'k' nearest neighbors' labels.",
        "default_params": {"n_neighbors": 5, "weights": "uniform"}
    },
    "bagging": {
        "name": "Ensemble Bagging (Decision Trees)",
        "type": "Supervised Ensemble (Bagging)",
        "inductive_bias": "Aggregates predictions from multiple base estimators to decrease variance.",
        "description": "Trains multiple base estimators (here, Decision Trees) in parallel on bootstrap samples of the training set.",
        "default_params": {"n_estimators": 30}
    },
    "boosting": {
        "name": "Ensemble Boosting (Gradient Boosting)",
        "type": "Supervised Ensemble (Boosting)",
        "inductive_bias": "Trains models sequentially, placing higher weights on instances misclassified by previous models.",
        "description": "Sequentially builds trees, where each new tree corrects the errors (residuals) of the existing trees.",
        "default_params": {"n_estimators": 50, "learning_rate": 0.1, "max_depth": 3}
    }
}

REGRESSORS_METADATA = {
    "simple_linear": {
        "name": "Simple Linear Regression",
        "type": "Supervised Learning (Regression)",
        "inductive_bias": "Assumes a straight-line linear relationship between a single predictor (Experience) and target (Salary).",
        "description": "Predicts a continuous variable based on a single input variable by fitting a linear equation.",
        "features": ["Experience_Years"]
    },
    "multiple_linear": {
        "name": "Multiple Linear Regression",
        "type": "Supervised Learning (Regression)",
        "inductive_bias": "Assumes a flat hyperplane linear relationship between multiple predictors and the target variable.",
        "description": "Models the relationship between two or more explanatory variables and a continuous response variable.",
        "features": ["Experience_Years", "Python_Score", "ML_Score", "SQL_Score", "WebDev_Score", "SystemDesign_Score", "Communication_Score", "Certifications_Count"]
    },
    "polynomial": {
        "name": "Polynomial Regression",
        "type": "Supervised Learning (Regression)",
        "inductive_bias": "Assumes a non-linear polynomial relationship between features and target, modeled linearly in higher-degree space.",
        "description": "Transforms variables into polynomial combinations (e.g., degree 2) and runs a linear regression over them.",
        "features": ["Experience_Years", "ML_Score"],
        "default_params": {"degree": 2}
    },
    "bayesian_linear": {
        "name": "Bayesian Linear Regression",
        "type": "Supervised Learning (Regression)",
        "inductive_bias": "Introduces probability distributions over parameters instead of point estimates. Applies L2 regularization via prior.",
        "description": "Formulates linear regression using probability distributions, providing uncertainty estimates for coefficients.",
        "features": ["Experience_Years", "Python_Score", "ML_Score", "SQL_Score", "WebDev_Score", "SystemDesign_Score", "Communication_Score", "Certifications_Count"]
    }
}

def get_classifier(model_name, params=None):
    """Instantiates the requested classifier with optional custom parameters."""
    if params is None:
        params = {}
        
    # Cast parameter values correctly
    clean_params = {}
    for k, v in params.items():
        if k in ["n_neighbors", "n_estimators", "max_depth", "min_samples_split", "max_iter"]:
            clean_params[k] = int(v) if v is not None else v
        elif k in ["C", "eta0", "learning_rate"]:
            clean_params[k] = float(v)
        else:
            clean_params[k] = v

    # Remove None values so defaults take over
    clean_params = {k: v for k, v in clean_params.items() if v is not None}

    if model_name == "logistic_regression":
        return LogisticRegression(**clean_params, random_state=42)
    elif model_name == "perceptron":
        return Perceptron(**clean_params, random_state=42)
    elif model_name == "naive_bayes":
        return GaussianNB()
    elif model_name == "svm":
        return SVC(**clean_params, random_state=42, probability=True)
    elif model_name == "decision_tree":
        return DecisionTreeClassifier(**clean_params, random_state=42)
    elif model_name == "random_forest":
        return RandomForestClassifier(**clean_params, random_state=42)
    elif model_name == "knn":
        return KNeighborsClassifier(**clean_params)
    elif model_name == "bagging":
        return BaggingClassifier(estimator=DecisionTreeClassifier(max_depth=5), **clean_params, random_state=42)
    elif model_name == "boosting":
        return GradientBoostingClassifier(**clean_params, random_state=42)
    else:
        raise ValueError(f"Unknown classifier model: {model_name}")

def get_regressor(model_name, params=None):
    """Instantiates the requested regressor with optional custom parameters."""
    if params is None:
        params = {}
        
    if model_name == "simple_linear":
        return LinearRegression()
    elif model_name == "multiple_linear":
        return LinearRegression()
    elif model_name == "polynomial":
        degree = int(params.get("degree", 2))
        # Returns a Pipeline of polynomial features + linear regression
        return make_pipeline(PolynomialFeatures(degree=degree), LinearRegression())
    elif model_name == "bayesian_linear":
        return BayesianRidge()
    else:
        raise ValueError(f"Unknown regressor model: {model_name}")
