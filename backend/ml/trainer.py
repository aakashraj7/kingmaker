import time
import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, MinMaxScaler, LabelEncoder
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, mean_squared_error, r2_score
from ml.dataset import generate_kaggle_dataset
from ml.models import get_classifier, get_regressor, CLASSIFIERS_METADATA, REGRESSORS_METADATA
from sklearn.cluster import KMeans

DATA_PATH = "data/career_data.csv"

def get_or_create_dataset():
    """Loads the dataset or generates it if missing."""
    if not os.path.exists(DATA_PATH):
        return generate_kaggle_dataset(DATA_PATH)
    return pd.read_csv(DATA_PATH)

def prepare_classification_data(df, test_size=0.2, scaling="standard", random_state=42):
    """
    Splits classification data, encodes categories, and applies optional scaling.
    """
    X = df[["Experience_Years", "Python_Score", "ML_Score", "SQL_Score", "WebDev_Score", "SystemDesign_Score", "Communication_Score", "Certifications_Count"]]
    y = df["Role"]
    
    # Label encode target variable
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)
    
    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(X, y_encoded, test_size=test_size, random_state=random_state, stratify=y_encoded)
    
    # Feature Scaling
    scaler = None
    if scaling == "standard":
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
    elif scaling == "minmax":
        scaler = MinMaxScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
    else:
        X_train_scaled = X_train.values
        X_test_scaled = X_test.values
        
    return X_train_scaled, X_test_scaled, y_train, y_test, le, scaler

def prepare_regression_data(df, feature_names, test_size=0.2, scaling="none", random_state=42):
    """
    Splits regression data and applies scaling if requested.
    """
    X = df[feature_names]
    y = df["Expected_Salary"]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=random_state)
    
    scaler = None
    if scaling == "standard":
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
    elif scaling == "minmax":
        scaler = MinMaxScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
    else:
        X_train_scaled = X_train.values
        X_test_scaled = X_test.values
        
    return X_train_scaled, X_test_scaled, y_train, y_test, scaler

def train_and_evaluate_classifier(model_name, test_size=0.2, scaling="standard", params=None):
    """Trains and returns metrics for a classifier model."""
    df = get_or_create_dataset()
    X_train, X_test, y_train, y_test, le, scaler = prepare_classification_data(df, test_size, scaling)
    
    clf = get_classifier(model_name, params)
    
    # Time the fitting process
    start_time = time.time()
    clf.fit(X_train, y_train)
    fit_time = round(time.time() - start_time, 4)
    
    # Predictions
    y_pred_train = clf.predict(X_train)
    y_pred_test = clf.predict(X_test)
    
    # Calculate classification metrics
    train_acc = float(round(accuracy_score(y_train, y_pred_train) * 100, 2))
    test_acc = float(round(accuracy_score(y_test, y_pred_test) * 100, 2))
    
    # Weighted metrics for multi-class
    precision = float(round(precision_score(y_test, y_pred_test, average='weighted', zero_division=0) * 100, 2))
    recall = float(round(recall_score(y_test, y_pred_test, average='weighted', zero_division=0) * 100, 2))
    f1 = float(round(f1_score(y_test, y_pred_test, average='weighted', zero_division=0) * 100, 2))
    
    # Cross Validation (5-Fold CV)
    cv_scores = cross_val_score(clf, X_train, y_train, cv=5)
    cv_mean = float(round(cv_scores.mean() * 100, 2))
    
    # Detect Overfitting vs Underfitting
    overfit_underfit = "Optimal"
    if train_acc - test_acc > 10.0:
        overfit_underfit = "Overfitting (High Train Acc, Low Test Acc)"
    elif train_acc < 60.0 and test_acc < 60.0:
        overfit_underfit = "Underfitting (Low Acc on both Train and Test)"
        
    return {
        "modelName": CLASSIFIERS_METADATA[model_name]["name"],
        "trainAccuracy": train_acc,
        "testAccuracy": test_acc,
        "precision": precision,
        "recall": recall,
        "f1Score": f1,
        "crossValScore": cv_mean,
        "fitTime": fit_time,
        "status": overfit_underfit,
        "inductiveBias": CLASSIFIERS_METADATA[model_name]["inductive_bias"]
    }

def train_and_evaluate_regressor(model_name, test_size=0.2, scaling="none", params=None):
    """Trains and returns metrics for a regressor model."""
    df = get_or_create_dataset()
    features = REGRESSORS_METADATA[model_name]["features"]
    
    X_train, X_test, y_train, y_test, scaler = prepare_regression_data(df, features, test_size, scaling)
    reg = get_regressor(model_name, params)
    
    start_time = time.time()
    reg.fit(X_train, y_train)
    fit_time = round(time.time() - start_time, 4)
    
    y_pred_train = reg.predict(X_train)
    y_pred_test = reg.predict(X_test)
    
    train_mse = float(round(mean_squared_error(y_train, y_pred_train), 4))
    test_mse = float(round(mean_squared_error(y_test, y_pred_test), 4))
    
    train_rmse = float(round(np.sqrt(train_mse), 4))
    test_rmse = float(round(np.sqrt(test_mse), 4))
    
    train_r2 = float(round(r2_score(y_train, y_pred_train) * 100, 2))
    test_r2 = float(round(r2_score(y_test, y_pred_test) * 100, 2))
    
    return {
        "modelName": REGRESSORS_METADATA[model_name]["name"],
        "trainMSE": train_mse,
        "testMSE": test_mse,
        "trainRMSE": train_rmse,
        "testRMSE": test_rmse,
        "trainR2": train_r2,
        "testR2": test_r2,
        "fitTime": fit_time,
        "inductiveBias": REGRESSORS_METADATA[model_name]["inductive_bias"]
    }

def get_kmeans_clusters(n_clusters=3):
    """Runs K-Means clustering on the skill dimensions and returns results."""
    df = get_or_create_dataset()
    skills = df[["Python_Score", "ML_Score", "SQL_Score", "WebDev_Score", "SystemDesign_Score", "Communication_Score"]]
    
    # Scale data for KMeans
    scaler = StandardScaler()
    skills_scaled = scaler.fit_transform(skills)
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(skills_scaled)
    
    # Add cluster label back to data to get averages
    df_clustered = df.copy()
    df_clustered["Cluster"] = clusters
    
    cluster_summaries = []
    # Identify labels based on dominating features
    for c_id in range(n_clusters):
        c_data = df_clustered[df_clustered["Cluster"] == c_id]
        avg_skills = c_data[["Python_Score", "ML_Score", "SQL_Score", "WebDev_Score", "SystemDesign_Score", "Communication_Score"]].mean().to_dict()
        
        # Determine archetype label
        max_skill = max(avg_skills, key=avg_skills.get)
        label_map = {
            "Python_Score": "Technical / Python Specialist",
            "ML_Score": "Machine Learning Scholar",
            "SQL_Score": "Database / Analyst Profile",
            "WebDev_Score": "Creative Frontend / Web Architect",
            "SystemDesign_Score": "Systems / Infrastructure Designer",
            "Communication_Score": "Leadership / Product Strategist"
        }
        
        cluster_summaries.append({
            "clusterId": c_id,
            "size": len(c_data),
            "label": label_map.get(max_skill, f"Archetype {c_id + 1}"),
            "centerAverages": {k.replace("_Score", ""): float(round(v, 1)) for k, v in avg_skills.items()}
        })
        
    return cluster_summaries

def precalculate_comparison_arena():
    """Generates comparison data for all classifiers using standard default configurations."""
    classifiers = ["logistic_regression", "perceptron", "naive_bayes", "svm", "decision_tree", "random_forest", "knn", "bagging", "boosting"]
    results = []
    for model in classifiers:
        try:
            res = train_and_evaluate_classifier(model, test_size=0.2, scaling="standard")
            results.append(res)
        except Exception as e:
            print(f"Error training model comparison for {model}: {e}")
    return results
