import os
import pandas as pd
import numpy as np

def generate_kaggle_dataset(output_path="data/career_data.csv"):
    """
    Generates a synthetic Kaggle-like dataset for career recommendation and salary prediction.
    Features are designed with realistic correlations to represent real-world distributions.
    """
    # Ensure data directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    np.random.seed(42)
    n_samples = 1200
    
    # Generate experience (0 to 15 years, biased towards early-to-mid career)
    exp = np.random.exponential(scale=4.0, size=n_samples)
    exp = np.clip(exp, 0, 15)
    
    # Generate scores (0 to 100) for different domains
    python = np.random.normal(loc=65, scale=18, size=n_samples)
    ml = np.random.normal(loc=55, scale=20, size=n_samples)
    sql = np.random.normal(loc=60, scale=15, size=n_samples)
    webdev = np.random.normal(loc=58, scale=20, size=n_samples)
    sys_design = np.random.normal(loc=50, scale=18, size=n_samples)
    comm = np.random.normal(loc=70, scale=12, size=n_samples)
    
    # Clip all scores between 0 and 100
    python = np.clip(python, 0, 100)
    ml = np.clip(ml, 0, 100)
    sql = np.clip(sql, 0, 100)
    webdev = np.clip(webdev, 0, 100)
    sys_design = np.clip(sys_design, 0, 100)
    comm = np.clip(comm, 0, 100)
    
    # Certifications count (0 to 5)
    certs = np.random.poisson(lam=1.5, size=n_samples)
    certs = np.clip(certs, 0, 5)
    
    # Assign Roles based on dominant skills (Classification Target)
    roles = []
    salaries = []
    
    roles_list = [
        "Machine Learning Engineer",
        "Data Analyst",
        "Cloud/DevOps Engineer",
        "Product Manager",
        "Cybersecurity Analyst",
        "UX Designer"
    ]
    
    for i in range(n_samples):
        # Determine classification role using scores
        scores = {
            "Machine Learning Engineer": ml[i]*0.5 + python[i]*0.3 + sys_design[i]*0.2,
            "Data Analyst": sql[i]*0.5 + python[i]*0.3 + comm[i]*0.2,
            "Cloud/DevOps Engineer": sys_design[i]*0.5 + python[i]*0.3 + sql[i]*0.2,
            "Product Manager": comm[i]*0.6 + sys_design[i]*0.4 + np.random.normal(10, 5),
            "Cybersecurity Analyst": sys_design[i]*0.4 + python[i]*0.3 + sql[i]*0.3 + np.random.normal(5, 5),
            "UX Designer": comm[i]*0.4 + webdev[i]*0.6
        }
        
        assigned_role = max(scores, key=scores.get)
        roles.append(assigned_role)
        
        # Determine salary (Regression Target) in INR Lakhs per annum (e.g. 4L to 35L)
        # Base salary depends on the role
        base_salary_map = {
            "Machine Learning Engineer": 9.5,
            "Data Analyst": 6.0,
            "Cloud/DevOps Engineer": 8.5,
            "Product Manager": 11.0,
            "Cybersecurity Analyst": 8.0,
            "UX Designer": 6.5
        }
        base = base_salary_map[assigned_role]
        
        # Salary grows with experience (non-linear growth) + skills + certifications + noise
        exp_multiplier = 1.8 * exp[i] - 0.05 * (exp[i]**2) # Quadratic relationship showing curve flattening
        skill_bonus = (python[i] + ml[i] + sys_design[i] + comm[i] + sql[i] + webdev[i]) / 60.0
        cert_bonus = certs[i] * 0.6
        
        noise = np.random.normal(0, 1.2)
        
        salary = base + exp_multiplier + skill_bonus + cert_bonus + noise
        salary = max(3.5, round(salary, 2)) # Minimum starting salary of 3.5L
        salaries.append(salary)
        
    # Create DataFrame
    df = pd.DataFrame({
        "Experience_Years": np.round(exp, 1),
        "Python_Score": np.round(python, 1),
        "ML_Score": np.round(ml, 1),
        "SQL_Score": np.round(sql, 1),
        "WebDev_Score": np.round(webdev, 1),
        "SystemDesign_Score": np.round(sys_design, 1),
        "Communication_Score": np.round(comm, 1),
        "Certifications_Count": certs,
        "Expected_Salary": salaries,
        "Role": roles
    })
    
    # Save to CSV
    df.to_csv(output_path, index=False)
    print(f"Generated synthetic dataset with {len(df)} records at: {output_path}")
    return df

if __name__ == "__main__":
    generate_kaggle_dataset()
