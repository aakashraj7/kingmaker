import random
from database import db
from services.llm_service import complete_json
from services import market_service

def score_roles_by_skill_overlap(user_skills=None):
    if user_skills is None:
        user_skills = []
    
    user_skills_set = set(s.lower().strip() for s in user_skills)
    roles = market_service.get_market_snapshot()["topRoles"]
    
    scored_roles = []
    for role in roles:
        required_skills = [s.lower() for s in role["keySkills"]]
        overlap = sum(1 for s in required_skills if s in user_skills_set)
        match_pct = int(round((overlap / len(required_skills)) * 100)) if required_skills else 0
        scored_roles.append({
            "role": role["name"],
            "matchPct": match_pct,
            "demandScore": role["demandScore"]
        })
        
    # Sort by matchPct, then demandScore
    return sorted(scored_roles, key=lambda x: (x["matchPct"], x["demandScore"]), reverse=True)

def generate_profile_insights(user_id: str):
    profile = db.profiles.find_one({"userId": user_id})
    if not profile:
        return None
        
    skills = profile.get("skillsList", [])
    role_matches = score_roles_by_skill_overlap(skills)
    top_matches = role_matches[:3]
    
    # Blended readiness score
    completeness = sum(1 for k in ["targetRole", "experienceLevel", "region", "expectedSalary"] if profile.get(k))
    completeness_pct = (completeness / 4.0) * 100
    skill_breadth = min(100, len(skills) * 8)
    best_match = top_matches[0]["matchPct"] if top_matches else 0
    
    readiness_score = int(round(completeness_pct * 0.3 + skill_breadth * 0.3 + best_match * 0.4))
    career_score = int(round(readiness_score * 0.9 + (10 if len(skills) > 0 else 0)))
    
    # Limit score boundaries
    readiness_score = max(0, min(100, readiness_score))
    career_score = max(0, min(100, career_score))
    
    system_prompt = (
        "You write short, honest career profile summaries from structured data. Respond with ONLY JSON: "
        '{"careerObjective": string, "currentLevel": string, "strengths": [string], "weaknesses": [string]}. '
        "Keep each string under 20 words. Base everything strictly on the given data - never invent skills or experience not listed."
    )
    
    skills_str = ", ".join(skills) if skills else "none listed"
    target_role = profile.get("targetRole", "not set")
    exp_level = profile.get("experienceLevel", "not set")
    matches_str = ", ".join(f"{m['role']} ({m['matchPct']}% match)" for m in top_matches) if top_matches else "none"
    
    user_prompt = (
        f"Skills: {skills_str}\nTarget role: {target_role}\nExperience level: {exp_level}\n"
        f"Top matching roles by skill overlap: {matches_str}"
    )
    
    res = complete_json(system_prompt, [{"role": "user", "content": user_prompt}])
    data = res["data"]
    stub = res["stub"]
    
    narrative = {
        "careerObjective": None,
        "currentLevel": profile.get("experienceLevel") or "Not set",
        "strengths": [],
        "weaknesses": []
    }
    
    if not stub and data:
        narrative["careerObjective"] = data.get("careerObjective")
        narrative["currentLevel"] = data.get("currentLevel") or narrative["currentLevel"]
        narrative["strengths"] = data.get("strengths") or []
        narrative["weaknesses"] = data.get("weaknesses") or []
    else:
        # Fallback values if offline
        narrative["careerObjective"] = f"Motivated candidate focused on establishing a career as a {target_role or 'professional'}."
        narrative["strengths"] = [f"Proficient in {skills[0]}" if skills else "Eager learner", "Strong foundation"]
        narrative["weaknesses"] = [f"Needs to build deep knowledge in {target_role}" if target_role != "not set" else "Needs skill profiling"]

    # Skill percentages (semi-randomized for demo/scoring display)
    skill_percentages = []
    for s in skills[:12]:
        skill_percentages.append({
            "name": s,
            "pct": int(round(55 + random.random() * 35))
        })
        
    updated = db.profiles.update_one(
        {"userId": user_id},
        {
            "$set": {
                "careerScore": career_score,
                "readinessScore": readiness_score,
                "recommendedRoles": top_matches,
                "careerObjective": narrative["careerObjective"],
                "strengths": narrative["strengths"],
                "weaknesses": narrative["weaknesses"],
                "skillPercentages": skill_percentages
            }
        }
    )
    return updated
