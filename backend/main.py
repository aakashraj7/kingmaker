import os
import shutil
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext
from jose import jwt, JWTError
from pydantic import BaseModel, EmailStr

# Import Database & Services
from database import db
from services import llm_service, market_service, resume_parser, achievements, profile_engine
from ml import dataset, trainer, models

# Environment config
SECRET_KEY = os.getenv("JWT_SECRET", "kingmaker-super-secret-key-321")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 hours

# Setup FastAPI
app = FastAPI(title="Kingmaker AI Career API", version="1.0.0")

# Security Hashing Setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Generate Dataset at startup if missing
trainer.get_or_create_dataset()

# JWT Helpers
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Authentication Dependency
class AuthUser:
    def __init__(self, user_id: str, is_guest: bool, email: Optional[str] = None, name: Optional[str] = None):
        self.id = user_id
        self.is_guest = is_guest
        self.email = email
        self.name = name

async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_guest_id: Optional[str] = Header(None)
) -> AuthUser:
    """
    Middleware decoding either Bearer JWT token or x-guest-id header.
    Maps to req.user in the Node.js implementation.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                raise HTTPException(status_code=401, detail="Invalid token subject.")
            
            # Fetch user from DB
            user = db.users.find_one({"_id": user_id})
            if not user:
                raise HTTPException(status_code=401, detail="User not found.")
                
            return AuthUser(user_id=user["id"], is_guest=False, email=user.get("email"), name=user.get("name"))
        except JWTError:
            raise HTTPException(status_code=401, detail="Token verification failed.")
            
    elif x_guest_id:
        # User is in guest mode
        return AuthUser(user_id=x_guest_id, is_guest=True, name="Guest Explorer")
        
    raise HTTPException(
        status_code=401,
        detail="Authentication credentials missing. Supply Bearer JWT or x-guest-id header."
    )

# Pydantic schemas
class SignupModel(BaseModel):
    email: EmailStr
    password: str
    name: str

class LoginModel(BaseModel):
    email: EmailStr
    password: str

class ChatMessageModel(BaseModel):
    message: str
    conversationId: Optional[str] = None

class ProfileUpdateModel(BaseModel):
    targetRole: Optional[str] = None
    experienceLevel: Optional[str] = None
    region: Optional[str] = None
    expectedSalary: Optional[str] = None

class RoadmapGenerateModel(BaseModel):
    targetRole: str

class SkillGapModel(BaseModel):
    targetRole: str

class InterviewQuestionsModel(BaseModel):
    targetRole: str
    count: Optional[int] = 5

class InterviewEvaluateModel(BaseModel):
    question: str
    answer: str

class SettingsUpdateModel(BaseModel):
    theme: Optional[str] = None
    notificationsEnabled: Optional[bool] = None
    language: Optional[str] = None

class TrainClassifierModel(BaseModel):
    modelName: str
    testSize: Optional[float] = 0.2
    scaling: Optional[str] = "standard"
    params: Optional[dict] = None

class TrainRegressorModel(BaseModel):
    modelName: str
    testSize: Optional[float] = 0.2
    scaling: Optional[str] = "none"
    params: Optional[dict] = None

# ==========================================
# HEALTH CHECK
# ==========================================
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "provider": llm_service.PROVIDER,
        "database": "mongodb" if db.use_real_mongo else "json-fallback",
        "time": datetime.utcnow().isoformat()
    }

# ==========================================
# AUTH SYSTEM
# ==========================================
@app.post("/api/auth/signup")
def signup(data: SignupModel):
    existing = db.users.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
        
    hashed = hash_password(data.password)
    user_id = str(uuid.uuid4())
    user_doc = {
        "_id": user_id,
        "email": data.email.lower(),
        "password": hashed,
        "name": data.name
    }
    
    # Save user
    db.users.insert_one(user_doc)
    
    # Create profile document
    profile_doc = {
        "_id": str(uuid.uuid4()),
        "userId": user_id,
        "name": data.name,
        "targetRole": "",
        "experienceLevel": "Student / Entry",
        "region": "",
        "expectedSalary": "",
        "skillsList": [],
        "careerScore": 0,
        "readinessScore": 0,
        "strengths": [],
        "weaknesses": []
    }
    db.profiles.insert_one(profile_doc)
    
    token = create_access_token({"sub": user_id})
    return {
        "token": token,
        "user": {"email": data.email.lower(), "name": data.name, "id": user_id}
    }

@app.post("/api/auth/login")
def login(data: LoginModel):
    user = db.users.find_one({"email": data.email.lower()})
    if not user or not verify_password(data.password, user["password"]):
        raise HTTPException(status_code=400, detail="Invalid email or password.")
        
    token = create_access_token({"sub": user["id"]})
    return {
        "token": token,
        "user": {"email": user["email"], "name": user["name"], "id": user["id"]}
    }

@app.post("/api/auth/guest")
def guest():
    guest_id = f"guest-{uuid.uuid4()}"
    
    # Initialize a profile document for guest
    profile_doc = {
        "_id": str(uuid.uuid4()),
        "userId": guest_id,
        "name": "Guest Explorer",
        "targetRole": "Machine Learning Engineer",
        "experienceLevel": "Student / Entry",
        "region": "Chennai, IN",
        "expectedSalary": "₹6L – ₹9L",
        "skillsList": ["Python", "SQL", "Communication"],
        "careerScore": 30,
        "readinessScore": 40,
        "strengths": ["Basic coding", "SQL syntax"],
        "weaknesses": ["Deployment", "Algorithms Core"]
    }
    db.profiles.insert_one(profile_doc)
    
    return {"guestId": guest_id}

# ==========================================
# CHAT SYSTEM
# ==========================================
@app.get("/api/chat/history")
def chat_history(user: AuthUser = Depends(get_current_user)):
    msgs = db.messages.find({"userId": user.id})
    # Sort messages
    msgs_sorted = sorted(msgs, key=lambda x: x.get("createdAt", ""))
    return {"messages": [{"role": m["role"], "text": m["content"]} for m in msgs_sorted]}

@app.post("/api/chat")
def chat(data: ChatMessageModel, user: AuthUser = Depends(get_current_user)):
    conv_id = data.conversationId or str(uuid.uuid4())
    
    # Save user message
    user_msg_doc = {
        "_id": str(uuid.uuid4()),
        "userId": user.id,
        "conversationId": conv_id,
        "role": "user",
        "content": data.message
    }
    db.messages.insert_one(user_msg_doc)
    
    # Fetch recent conversation context (last 10 messages)
    history_docs = db.messages.find({"userId": user.id, "conversationId": conv_id})
    history_docs = sorted(history_docs, key=lambda x: x.get("createdAt", ""))[-10:]
    
    history = [{"role": m["role"], "content": m["content"]} for m in history_docs]
    
    # Fetch user's profile and files for context
    profile = db.profiles.find_one({"userId": user.id}) or {}
    resume_files = list(db.files.find({"userId": user.id, "category": "resume"}))
    
    resume_context = ""
    if resume_files:
        try:
            # Sort by creation date or use the last one
            latest_resume = sorted(resume_files, key=lambda x: x.get("createdAt", ""))[-1]
            raw_text = resume_parser.extract_text(latest_resume["path"], latest_resume["originalName"])
            resume_context = raw_text[:5000] # Cap to prevent inflating token usage
        except Exception as e:
            print(f"Error reading resume for chat context: {e}")
            
    profile_context = (
        f"Target Career: {profile.get('targetRole') or 'Not specified'}\n"
        f"Experience Level: {profile.get('experienceLevel') or 'Not specified'}\n"
        f"Skills List: {', '.join(profile.get('skillsList', [])) if profile.get('skillsList') else 'None'}\n"
        f"Strengths: {', '.join(profile.get('strengths', [])) if profile.get('strengths') else 'None'}\n"
        f"Areas to improve: {', '.join(profile.get('weaknesses', [])) if profile.get('weaknesses') else 'None'}\n"
    )
    
    system_prompt = (
        "You are the Kingmaker Career Guidance Bot, a premium AI career advisor.\n"
        "Here is the context about the user's profile:\n"
        f"{profile_context}\n"
    )
    
    if resume_context:
        system_prompt += (
            f"Here is the raw text extracted from the user's uploaded resume:\n"
            f"\"\"\"\n{resume_context}\n\"\"\"\n"
            "You have direct access to their resume. Use it to answer questions about their background, projects, work experience, education, or skills. "
            "If they ask to review, analyze, or give feedback on their resume, analyze this text and provide constructive feedback with strengths and improvement areas.\n"
        )
    else:
        system_prompt += (
            "The user has not uploaded a resume yet. If they ask about their resume, politely explain that "
            "you can't see it yet, and ask them to upload it in the 'Upload Files' section so you can analyze it.\n"
        )
        
    system_prompt += (
        "\nProvide constructive, practical, and highly engaging advice about career paths, skills, "
        "and closing knowledge gaps. Use concise paragraphs or clear bullet points. "
        "Keep responses under 150 words unless detail is requested."
    )
    
    res = llm_service.complete(system_prompt, history)
    bot_reply = res["text"]
    
    # Save bot message
    bot_msg_doc = {
        "_id": str(uuid.uuid4()),
        "userId": user.id,
        "conversationId": conv_id,
        "role": "bot",
        "content": bot_reply
    }
    db.messages.insert_one(bot_msg_doc)
    
    # Evaluate Achievements
    ach_res = achievements.evaluate(user.id)
    
    # Create notification triggers for newly unlocked achievements
    for a in ach_res["newly"]:
        db.notifications.insert_one({
            "_id": str(uuid.uuid4()),
            "userId": user.id,
            "title": "Achievement Unlocked!",
            "message": f"You unlocked '{a['name']}' - {a['desc']}",
            "type": "achievement",
            "read": False,
            "silent": False
        })
        
    return {
        "conversationId": conv_id,
        "reply": bot_reply,
        "unlockedAchievements": ach_res["newly"]
    }

# ==========================================
# FILE UPLOAD SYSTEM
# ==========================================
@app.get("/api/upload")
def list_files(user: AuthUser = Depends(get_current_user)):
    files = db.files.find({"userId": user.id})
    return {
        "files": [{
            "id": f["id"],
            "name": f["originalName"],
            "size": f["size"],
            "category": f["category"],
            "status": f["status"]
        } for f in files]
    }

@app.post("/api/upload")
def upload_file(file: UploadFile = File(...), user: AuthUser = Depends(get_current_user)):
    file_id = str(uuid.uuid4())
    _, ext = os.path.splitext(file.filename.lower())
    
    # Save file locally
    saved_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")
    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Read file size
    size_bytes = os.path.getsize(saved_path)
    
    # Determine category
    category = "document"
    fn_lower = file.filename.lower()
    if "resume" in fn_lower or "cv" in fn_lower:
        category = "resume"
    elif any(x in fn_lower for x in ["cert", "nanodegree", "diploma", "badge", "license"]):
        category = "certificate"
        
    # Save file record in db
    file_doc = {
        "_id": file_id,
        "userId": user.id,
        "originalName": file.filename,
        "path": saved_path,
        "size": size_bytes,
        "category": category,
        "status": "processed"
    }
    db.files.insert_one(file_doc)
    
    # If resume, extract text and parse skills
    if category == "resume":
        text = resume_parser.extract_text(saved_path, file.filename)
        if text:
            parsed = resume_parser.structure_resume(text)
            
            # Update profile with parsed skills
            profile = db.profiles.find_one({"userId": user.id})
            if profile:
                # Merge existing skills or overwrite
                existing_skills = profile.get("skillsList", [])
                new_skills = parsed.get("skills", [])
                merged_skills = list(set(existing_skills + new_skills))
                
                db.profiles.update_one(
                    {"userId": user.id},
                    {
                        "$set": {
                            "skillsList": merged_skills,
                            "targetRole": parsed.get("name") if not profile.get("targetRole") else profile.get("targetRole")
                        }
                    }
                )
                # Compute insights and blended score
                profile_engine.generate_profile_insights(user.id)
                
    # Evaluate Achievements
    ach_res = achievements.evaluate(user.id)
    for a in ach_res["newly"]:
        db.notifications.insert_one({
            "_id": str(uuid.uuid4()),
            "userId": user.id,
            "title": "Achievement Unlocked!",
            "message": f"You unlocked '{a['name']}' - {a['desc']}",
            "type": "achievement",
            "read": False,
            "silent": False
        })
        
    return {
        "file": {
            "id": file_id,
            "name": file.filename,
            "category": category
        },
        "unlockedAchievements": ach_res["newly"]
    }

@app.delete("/api/upload/{file_id}")
def delete_file(file_id: str, user: AuthUser = Depends(get_current_user)):
    f = db.files.find_one({"userId": user.id, "_id": file_id})
    if not f:
        raise HTTPException(status_code=404, detail="File not found.")
        
    # Delete physical file
    try:
        if os.path.exists(f["path"]):
            os.remove(f["path"])
    except Exception:
        pass
        
    db.files.delete_one({"_id": file_id})
    return {"status": "removed"}

# ==========================================
# PROFILE MANAGEMENT
# ==========================================
@app.get("/api/profile")
def get_profile(user: AuthUser = Depends(get_current_user)):
    profile = db.profiles.find_one({"userId": user.id})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return {"profile": profile}

@app.put("/api/profile")
def update_profile(data: ProfileUpdateModel, user: AuthUser = Depends(get_current_user)):
    profile = db.profiles.find_one({"userId": user.id})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")
        
    patch = {}
    if data.targetRole is not None: patch["targetRole"] = data.targetRole
    if data.experienceLevel is not None: patch["experienceLevel"] = data.experienceLevel
    if data.region is not None: patch["region"] = data.region
    if data.expectedSalary is not None: patch["expectedSalary"] = data.expectedSalary
    
    if patch:
        db.profiles.update_one({"userId": user.id}, {"$set": patch})
        # Recalculate profile metrics
        profile_engine.generate_profile_insights(user.id)
        
    # Check Achievements
    ach_res = achievements.evaluate(user.id)
    return {
        "profile": db.profiles.find_one({"userId": user.id}),
        "unlockedAchievements": ach_res["newly"]
    }

# ==========================================
# ROADMAP GENERATION
# ==========================================
@app.get("/api/roadmap")
def list_roadmaps(user: AuthUser = Depends(get_current_user)):
    rms = db.roadmaps.find({"userId": user.id})
    # Sort roadmaps by date descending
    rms_sorted = sorted(rms, key=lambda x: x.get("createdAt", ""), reverse=True)
    return {"roadmaps": rms_sorted}

@app.post("/api/roadmap")
def generate_roadmap(data: RoadmapGenerateModel, user: AuthUser = Depends(get_current_user)):
    profile = db.profiles.find_one({"userId": user.id})
    user_skills = profile.get("skillsList", []) if profile else []
    
    system_prompt = (
        "You write highly structured, practical, personalized career roadmaps in JSON format. "
        "Respond with ONLY a single valid JSON object matching this schema exactly:\n"
        '{"targetRole": string, "timelineMonths": number, "weeklyGoals": [string], '
        '"monthlyGoals": [{"month": number, "goal": string}], "courses": [string], "projects": [string], '
        '"certifications": [string], "interviewPrep": [string], "portfolioIdeas": [string]}. '
        "Do not wrap in prose or backticks. Keep bullet points direct, technical, and accurate for the role."
    )
    
    user_prompt = (
        f"Generate a personalized learning path for: {data.targetRole}.\n"
        f"My current skills: {', '.join(user_skills) if user_skills else 'None listed'}.\n"
        f"Target role: {data.targetRole}"
    )
    
    res = llm_service.complete_json(system_prompt, [{"role": "user", "content": user_prompt}])
    data_json = res["data"]
    stub = res["stub"]
    
    roadmap_doc = {
        "_id": str(uuid.uuid4()),
        "userId": user.id,
        "targetRole": data.targetRole,
        "body": data_json or {
            "targetRole": data.targetRole,
            "timelineMonths": 6,
            "weeklyGoals": ["Learn basic syntax for the role", "Research top frameworks"],
            "monthlyGoals": [{"month": 1, "goal": "Setup development environment and build basic project"}],
            "courses": ["Introductory tutorials"],
            "projects": ["Baseline sandbox app"],
            "certifications": [],
            "interviewPrep": [],
            "portfolioIdeas": []
        }
    }
    db.roadmaps.insert_one(roadmap_doc)
    
    # Evaluate Achievements
    ach_res = achievements.evaluate(user.id)
    return {
        "roadmap": roadmap_doc,
        "unlockedAchievements": ach_res["newly"]
    }

# ==========================================
# MARKET SIGNALsnapshots
# ==========================================
@app.get("/api/market")
def get_market(user: AuthUser = Depends(get_current_user)):
    snapshot = market_service.get_market_snapshot()
    
    # Add a market view notification to track achievements count
    db.notifications.insert_one({
        "_id": str(uuid.uuid4()),
        "userId": user.id,
        "title": "Market Checked",
        "message": "Viewed live job signals",
        "type": "market_view",
        "read": True,
        "silent": True
    })
    
    # Re-evaluate to check if unlocked explorer badge
    achievements.evaluate(user.id)
    
    return {"market": snapshot}

# ==========================================
# ADDITIONAL TOOLS
# ==========================================
@app.post("/api/tools/skill-gap")
def skill_gap(data: SkillGapModel, user: AuthUser = Depends(get_current_user)):
    profile = db.profiles.find_one({"userId": user.id})
    user_skills = set(s.lower().strip() for s in (profile.get("skillsList", []) if profile else []))
    
    required = market_service.get_required_skills_for_role(data.targetRole)
    if not required:
        raise HTTPException(
            status_code=404,
            detail=f"No skill map for '{data.targetRole}'. Known roles: {', '.join(market_service.list_known_roles())}"
        )
        
    missing = [s for s in required if s.lower() not in user_skills]
    present = [s for s in required if s.lower() in user_skills]
    
    system_prompt = (
        "You produce prioritized learning resources for missing career skills. Respond with ONLY JSON: "
        '{"priorityOrder": [string], "items": [{"skill": string, "difficulty": "beginner"|"intermediate"|"advanced", "estimatedWeeks": number, "resources": [string]}]}'
    )
    
    user_prompt = f"Missing skills for {data.targetRole}: {', '.join(missing) if missing else 'none'}"
    res = llm_service.complete_json(system_prompt, [{"role": "user", "content": user_prompt}])
    data_json = res["data"]
    
    return {
        "targetRole": data.targetRole,
        "alreadyHave": present,
        "missingSkills": missing,
        "plan": data_json or {
            "priorityOrder": missing,
            "items": [{"skill": m, "difficulty": "intermediate", "estimatedWeeks": 3, "resources": []} for m in missing]
        }
    }

@app.post("/api/tools/interview/questions")
def interview_questions(data: InterviewQuestionsModel, user: AuthUser = Depends(get_current_user)):
    system_prompt = (
        f"Generate mock interview questions. Respond with ONLY JSON: "
        f'{{"questions": [string]}}. Exactly {data.count} questions, mixing technical and behavioral, '
        f"appropriate for the given role."
    )
    user_prompt = f"Role: {data.targetRole}"
    res = llm_service.complete_json(system_prompt, [{"role": "user", "content": user_prompt}])
    data_json = res["data"]
    
    return {
        "targetRole": data.targetRole,
        "questions": data_json.get("questions", []) if data_json else [],
        "aiConfigured": not res["stub"]
    }

@app.post("/api/tools/interview/evaluate")
def interview_evaluate(data: InterviewEvaluateModel, user: AuthUser = Depends(get_current_user)):
    system_prompt = (
        "You evaluate mock interview answers. Respond with ONLY JSON: "
        '{"score": number (0-100), "feedback": string, "improvementSuggestions": [string]}. '
        "Be honest, constructive, and highly specific."
    )
    user_prompt = f"Question: {data.question}\nCandidate's answer: {data.answer}"
    res = llm_service.complete_json(system_prompt, [{"role": "user", "content": user_prompt}])
    data_json = res["data"]
    
    return data_json or {
        "score": 50,
        "feedback": "AI evaluation simulated offline. Configure GEMINI_API_KEY to receive custom AI scoring.",
        "improvementSuggestions": ["Include more concrete engineering examples in your answers."]
    }

@app.get("/api/tools/learning-recommendations")
def learning_recommendations(user: AuthUser = Depends(get_current_user)):
    profile = db.profiles.find_one({"userId": user.id})
    target_role = profile.get("targetRole", "Machine Learning Engineer") if profile else "Machine Learning Engineer"
    skills = profile.get("skillsList", []) if profile else []
    weaknesses = profile.get("weaknesses", []) if profile else []
    
    system_prompt = (
        "Recommend learning resources. Respond with ONLY JSON: "
        '{"courses": [string], "books": [string], "youtubePlaylists": [string], "certifications": [string], "projects": [string]}. '
        "Keep each list to 3-5 items, real and well-known where possible."
    )
    user_prompt = (
        f"Target role: {target_role}\n"
        f"Current skills: {', '.join(skills) if skills else 'none'}\n"
        f"Weaknesses: {', '.join(weaknesses) if weaknesses else 'unknown'}"
    )
    res = llm_service.complete_json(system_prompt, [{"role": "user", "content": user_prompt}])
    data_json = res["data"]
    
    return data_json or {
        "courses": ["Intro to Machine Learning (Coursera/Andrew Ng)", "Fast.ai Practical Deep Learning for Coders"],
        "books": ["Introduction to Probability by Joseph K. Blitzstein", "Python Data Science Handbook"],
        "youtubePlaylists": ["StatQuest by Josh Starmer", "3Blue1Brown Neural Networks"],
        "certifications": ["Google Cloud Certified Professional Machine Learning Engineer"],
        "projects": ["Build a simple neural net from scratch in NumPy", "Implement cross-validation on Kaggle datasets"],
        "note": "AI service not configured."
    }

@app.get("/api/tools/achievements")
def list_user_achievements(user: AuthUser = Depends(get_current_user)):
    return {"achievements": achievements.full_list(user.id)}

@app.get("/api/tools/dashboard")
def get_dashboard(user: AuthUser = Depends(get_current_user)):
    profile = db.profiles.find_one({"userId": user.id})
    roadmaps = db.roadmaps.find({"userId": user.id})
    messages = db.messages.find({"userId": user.id, "role": "user"})
    files = db.files.find({"userId": user.id})
    unlocked_ach = db.achievements.find({"userId": user.id})
    
    recent_activity = []
    for m in messages[-5:]:
        recent_activity.append({"type": "chat", "detail": m["content"][:80], "at": m["createdAt"]})
    for f in files[-5:]:
        recent_activity.append({"type": "upload", "detail": f["originalName"], "at": f["createdAt"]})
    for r in roadmaps[-5:]:
        recent_activity.append({"type": "roadmap", "detail": r["targetRole"], "at": r["createdAt"]})
        
    recent_activity = sorted(recent_activity, key=lambda x: x["at"], reverse=True)[:10]
    
    has_resume = any(f["category"] == "resume" for f in files)
    
    return {
        "careerScore": profile.get("careerScore", 0) if profile else 0,
        "resumeScore": 78 if has_resume else 0,
        "skillProgress": profile.get("skillPercentages", []) if profile else [],
        "applications": 0,
        "roadmapProgress": len(roadmaps),
        "achievementProgress": f"{len(unlocked_ach)}/{len(achievements.CATALOG)}",
        "recentActivity": recent_activity
    }

@app.get("/api/tools/settings")
def get_settings(user: AuthUser = Depends(get_current_user)):
    profile = db.profiles.find_one({"userId": user.id})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return {
        "theme": profile.get("theme", "dark"),
        "notificationsEnabled": profile.get("notificationsEnabled") != False,
        "preferredAIModel": llm_service.PROVIDER,
        "language": profile.get("language", "en")
    }

@app.put("/api/tools/settings")
def update_settings(data: SettingsUpdateModel, user: AuthUser = Depends(get_current_user)):
    profile = db.profiles.find_one({"userId": user.id})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")
        
    patch = {}
    if data.theme is not None: patch["theme"] = data.theme
    if data.notificationsEnabled is not None: patch["notificationsEnabled"] = data.notificationsEnabled
    if data.language is not None: patch["language"] = data.language
    
    if patch:
        db.profiles.update_one({"userId": user.id}, {"$set": patch})
        
    return {"settings": db.profiles.find_one({"userId": user.id})}

# ==========================================
# ML LAB & DATASET EXPLORER ENDPOINTS
# ==========================================
@app.get("/api/ml/dataset")
def get_ml_dataset():
    """Returns dataset summary stats, column descriptions, and first 30 rows."""
    try:
        df = trainer.get_or_create_dataset()
        
        # Calculate stats
        import pandas as pd
        summary = []
        for col in df.columns:
            if df[col].dtype in ['int64', 'float64', 'int32', 'float32']:
                mean_val = df[col].mean()
                std_val = df[col].std()
                min_val = df[col].min()
                max_val = df[col].max()
                summary.append({
                    "column": col,
                    "type": str(df[col].dtype),
                    "mean": float(round(mean_val, 2)) if pd.notnull(mean_val) else 0.0,
                    "std": float(round(std_val, 2)) if pd.notnull(std_val) else 0.0,
                    "min": float(round(min_val, 2)) if pd.notnull(min_val) else 0.0,
                    "max": float(round(max_val, 2)) if pd.notnull(max_val) else 0.0,
                    "missing": int(df[col].isnull().sum())
                })
            else:
                summary.append({
                    "column": col,
                    "type": str(df[col].dtype),
                    "mean": "N/A",
                    "std": "N/A",
                    "min": "N/A",
                    "max": "N/A",
                    "missing": int(df[col].isnull().sum())
                })
                
        # Generate correlation matrix for numerical features
        num_cols = df.select_dtypes(include=['int64', 'float64']).columns
        corr = json.loads(df[num_cols].corr().round(2).to_json())
        
        # Get first 30 sample rows
        samples = json.loads(df.head(35).to_json(orient="records"))
        
        return {
            "totalRows": len(df),
            "columns": list(df.columns),
            "summary": summary,
            "samples": samples,
            "correlation": corr
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {str(e)}")

@app.post("/api/ml/train/classifier")
def train_classifier(data: TrainClassifierModel):
    """Trains a classifier with hyperparameter inputs and returns accuracy, precision, f1."""
    try:
        results = trainer.train_and_evaluate_classifier(
            model_name=data.modelName,
            test_size=data.testSize,
            scaling=data.scaling,
            params=data.params
        )
        return results
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model training crashed: {str(e)}")

@app.post("/api/ml/train/regressor")
def train_regressor(data: TrainRegressorModel):
    """Trains a regressor with inputs and returns MSE and RMSE metrics."""
    try:
        results = trainer.train_and_evaluate_regressor(
            model_name=data.modelName,
            test_size=data.testSize,
            scaling=data.scaling,
            params=data.params
        )
        return results
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model training crashed: {str(e)}")

@app.get("/api/ml/compare")
def get_model_comparison():
    """Runs default training on all classifiers to build a comparative table."""
    try:
        results = trainer.precalculate_comparison_arena()
        return {"comparison": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ml/cluster")
def get_clusters(nClusters: int = Query(3, ge=2, le=6)):
    """Runs K-Means clustering on skills features and returns archetypes."""
    try:
        results = trainer.get_kmeans_clusters(n_clusters=nClusters)
        return {"clusters": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
