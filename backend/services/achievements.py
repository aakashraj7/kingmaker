from datetime import datetime
import uuid
from database import db

CATALOG = [
    { "key": "first_conversation", "icon": "💬", "name": "First Conversation", "desc": "Chatted with the Guidance Bot" },
    { "key": "document_ready", "icon": "📄", "name": "Document Ready", "desc": "Uploaded your first file" },
    { "key": "profile_complete", "icon": "🎯", "name": "First Steps", "desc": "Completed your career profile" },
    { "key": "market_explorer", "icon": "📊", "name": "Market Explorer", "desc": "Viewed live market data 5 times" },
    { "key": "path_finder", "icon": "🧭", "name": "Path Finder", "desc": "Received your first career roadmap" },
    { "key": "ten_questions", "icon": "🔥", "name": "Curious Mind", "desc": "Asked 10 questions" },
    { "key": "career_score_80", "icon": "🏆", "name": "Career Score 80+", "desc": "Reached a career readiness score of 80" },
    { "key": "certificate_uploaded", "icon": "📜", "name": "Certified", "desc": "Uploaded a certificate" }
]

def unlocked_set(user_id: str) -> set:
    records = db.achievements.find({"userId": user_id})
    return set(r["key"] for r in records)

def unlock(user_id: str, key: str):
    already = db.achievements.find_one({"userId": user_id, "key": key})
    if already:
        return None
        
    meta = next((c for c in CATALOG if c["key"] == key), None)
    if not meta:
        return None
        
    doc = {
        "_id": str(uuid.uuid4()),
        "userId": user_id,
        "key": key,
        "icon": meta["icon"],
        "name": meta["name"],
        "desc": meta["desc"],
        "unlockedAt": datetime.utcnow().isoformat()
    }
    return db.achievements.insert_one(doc)

def evaluate(user_id: str) -> dict:
    """Recomputes achievements against live usage metrics and returns newly unlocked ones."""
    message_count = len(db.messages.find({"userId": user_id, "role": "user"}))
    file_count = len(db.files.find({"userId": user_id}))
    cert_count = len(db.files.find({"userId": user_id, "category": "certificate"}))
    roadmap_count = len(db.roadmaps.find({"userId": user_id}))
    
    # We will log notifications or custom records for market_view counts
    market_views = len(db.notifications.find({"userId": user_id, "type": "market_view"}))
    profile = db.profiles.find_one({"userId": user_id})
    
    newly = []
    
    if message_count >= 1:
        u = unlock(user_id, "first_conversation")
        if u: newly.append(u)
    if message_count >= 10:
        u = unlock(user_id, "ten_questions")
        if u: newly.append(u)
    if file_count >= 1:
        u = unlock(user_id, "document_ready")
        if u: newly.append(u)
    if cert_count >= 1:
        u = unlock(user_id, "certificate_uploaded")
        if u: newly.append(u)
    if roadmap_count >= 1:
        u = unlock(user_id, "path_finder")
        if u: newly.append(u)
    if market_views >= 5:
        u = unlock(user_id, "market_explorer")
        if u: newly.append(u)
        
    if profile and profile.get("targetRole") and profile.get("experienceLevel") and profile.get("region"):
        u = unlock(user_id, "profile_complete")
        if u: newly.append(u)
        
    if profile and profile.get("careerScore", 0) >= 80:
        u = unlock(user_id, "career_score_80")
        if u: newly.append(u)
        
    return {
        "newly": newly,
        "all": full_list(user_id)
    }

def full_list(user_id: str) -> list:
    unlocked = db.achievements.find({"userId": user_id})
    unlocked_keys = set(u["key"] for u in unlocked)
    
    result = []
    for c in CATALOG:
        is_unlocked = c["key"] in unlocked_keys
        unlocked_doc = next((u for u in unlocked if u["key"] == c["key"]), None)
        result.append({
            "key": c["key"],
            "icon": c["icon"],
            "name": c["name"],
            "desc": c["desc"],
            "unlocked": is_unlocked,
            "unlockedAt": unlocked_doc["unlockedAt"] if unlocked_doc else None
        })
    return result
