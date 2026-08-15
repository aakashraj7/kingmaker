import time
from datetime import datetime

BASE_ROLES = [
    { "name": "Machine Learning Engineer", "basePct": 91, "baseSalaryLPA": [8, 22], "skills": ["Python", "PyTorch", "MLOps", "SQL", "Statistics"] },
    { "name": "Data Analyst", "basePct": 84, "baseSalaryLPA": [5, 12], "skills": ["SQL", "Excel", "Power BI", "Python", "Statistics"] },
    { "name": "Cloud / DevOps Engineer", "basePct": 82, "baseSalaryLPA": [7, 18], "skills": ["AWS", "Docker", "Kubernetes", "CI/CD", "Linux"] },
    { "name": "Product Manager", "basePct": 75, "baseSalaryLPA": [9, 24], "skills": ["Roadmapping", "SQL", "User Research", "Communication", "Analytics"] },
    { "name": "Cybersecurity Analyst", "basePct": 79, "baseSalaryLPA": [6, 16], "skills": ["Network Security", "SIEM", "Python", "Risk Assessment"] },
    { "name": "UX Designer", "basePct": 68, "baseSalaryLPA": [5, 13], "skills": ["Figma", "User Research", "Prototyping", "Design Systems"] },
    { "name": "Full-Stack Developer", "basePct": 88, "baseSalaryLPA": [5, 16], "skills": ["JavaScript", "React", "Node.js", "SQL", "System Design"] },
    { "name": "Data Scientist", "basePct": 86, "baseSalaryLPA": [8, 20], "skills": ["Python", "Statistics", "Machine Learning", "SQL", "Communication"] },
]

TRENDING_SKILLS = [
    "Python", "LLM Tooling", "Cloud (AWS/GCP)", "SQL", "Prompt Engineering",
    "Data Visualization", "Kubernetes", "Product Sense", "TypeScript", "MLOps"
]

def seeded_drift(key: str) -> float:
    """Deterministic-but-drifting pseudo-random number in [-1, 1], seeded by day + key"""
    day = datetime.utcnow().strftime("%Y-%m-%d")
    s = day + key
    h = 0
    for char in s:
        h = (h * 31 + ord(char)) & 0xFFFFFFFF
    return (h % 2000) / 1000.0 - 1.0

def get_market_snapshot():
    roles = []
    for i, r in enumerate(BASE_ROLES):
        drift = seeded_drift(r["name"])
        pct = max(50, min(99, int(round(r["basePct"] + drift * 4))))
        trend_pct = round((6.0 + drift * 5.0), 1)
        roles.append({
            "rank": i + 1,
            "name": r["name"],
            "demandScore": pct,
            "trend": f"{'+' if trend_pct >= 0 else ''}{trend_pct}%",
            "salaryRangeLPA": r["baseSalaryLPA"],
            "keySkills": r["skills"]
        })
        
    roles = sorted(roles, key=lambda x: x["demandScore"], reverse=True)
    for idx, role in enumerate(roles):
        role["rank"] = idx + 1
        
    drift_signals = seeded_drift("signals")
    drift_salary = seeded_drift("salary")
    drift_gaps = seeded_drift("gaps")
    
    active_signals_k = int(round(120 + drift_signals * 15))
    avg_entry_salary_l = round((7.4 + drift_salary * 1.2), 1)
    skill_gap_alerts = int(round(10 + drift_gaps * 4)) + 4
    
    return {
        "generatedAt": datetime.utcnow().isoformat(),
        "source": "mock (deterministic, swap in Adzuna/JSearch for live data)",
        "summary": {
            "activeJobSignals": f"{active_signals_k}K",
            "avgEntrySalary": f"₹{avg_entry_salary_l}L",
            "automationRiskAvg": "Low-Moderate",
            "skillGapAlerts": skill_gap_alerts
        },
        "topRoles": roles,
        "trendingSkills": TRENDING_SKILLS
    }

def get_role_detail(role_name: str):
    snapshot = get_market_snapshot()
    for r in snapshot["topRoles"]:
        if r["name"].lower() == role_name.lower():
            return r
    return None

def list_known_roles():
    return [r["name"] for r in BASE_ROLES]

def get_required_skills_for_role(role_name: str):
    for r in BASE_ROLES:
        if r["name"].lower() == role_name.lower():
            return r["skills"]
    return []
