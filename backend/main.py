import os
import shutil
import uuid
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
import bcrypt
from jose import jwt, JWTError
from pydantic import BaseModel, EmailStr, field_validator

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

# Security Hashing & Rate Limiting Setup
def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False

# Precompute dummy hash to mitigate timing attacks on nonexistent accounts
DUMMY_HASH = hash_password("dummy_constant_time_comparison_string")

FAILED_LOGIN_ATTEMPTS = defaultdict(list)
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 300 # 5 minutes

SIGNUP_ATTEMPTS = defaultdict(list)
MAX_SIGNUPS_PER_WINDOW = 10
SIGNUP_WINDOW_SECONDS = 300

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
    if authorization and isinstance(authorization, str) and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                raise HTTPException(status_code=401, detail="Invalid token subject.")
            
            # Fetch user from DB (support both _id and id query)
            user = db.users.find_one({"_id": user_id}) or db.users.find_one({"id": user_id})
            if not user:
                raise HTTPException(status_code=401, detail="User not found.")
                
            actual_id = str(user.get("id") or user.get("_id"))
            return AuthUser(user_id=actual_id, is_guest=False, email=user.get("email"), name=user.get("name"))
        except JWTError:
            raise HTTPException(status_code=401, detail="Token verification failed.")
            
    elif x_guest_id and isinstance(x_guest_id, str):
        clean_guest_id = str(x_guest_id).strip()
        # Security: ensure guest IDs strictly follow guest format and cannot spoof real user IDs
        if not clean_guest_id.startswith("guest-") or len(clean_guest_id) < 10:
            raise HTTPException(status_code=401, detail="Invalid guest identifier format.")
        if db.users.find_one({"_id": clean_guest_id}) or db.users.find_one({"id": clean_guest_id}):
            raise HTTPException(status_code=401, detail="Invalid guest credentials.")
        return AuthUser(user_id=clean_guest_id, is_guest=True, name="Guest Explorer")
        
    raise HTTPException(
        status_code=401,
        detail="Authentication credentials missing. Supply Bearer JWT or x-guest-id header."
    )

# Pydantic schemas with security validations
class SignupModel(BaseModel):
    email: EmailStr
    password: str
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        clean = v.strip()
        if len(clean) < 2:
            raise ValueError("Name must be at least 2 characters long.")
        if len(clean) > 60:
            raise ValueError("Name cannot exceed 60 characters.")
        return clean

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password cannot exceed 72 bytes.")
        has_letter = any(c.isalpha() for c in v)
        has_digit_or_special = any(not c.isalpha() for c in v)
        if not (has_letter and has_digit_or_special):
            raise ValueError("Password must contain at least one letter and at least one number or special symbol.")
        return v

class LoginModel(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_login_password(cls, v: str) -> str:
        if not v:
            raise ValueError("Password is required.")
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password exceeds maximum allowed length.")
        return v

class ChatMessageModel(BaseModel):
    message: str
    conversationId: Optional[str] = None

class NewConversationModel(BaseModel):
    title: Optional[str] = "New Conversation"

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

class OnboardingCompleteModel(BaseModel):
    targetRole: str
    experienceLevel: str
    region: str
    expectedSalary: str

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
def signup(data: SignupModel, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    # Rate limiting for signup
    recent_signups = [t for t in SIGNUP_ATTEMPTS[client_ip] if now - t < SIGNUP_WINDOW_SECONDS]
    SIGNUP_ATTEMPTS[client_ip] = recent_signups
    if len(recent_signups) >= MAX_SIGNUPS_PER_WINDOW:
        raise HTTPException(
            status_code=429,
            detail="Too many signup attempts from this network. Please try again in 5 minutes."
        )

    clean_email = data.email.strip().lower()
    clean_name = data.name.strip()

    existing = db.users.find_one({"email": clean_email})
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
        
    hashed = hash_password(data.password)
    user_id = str(uuid.uuid4())
    user_doc = {
        "_id": user_id,
        "id": user_id,
        "email": clean_email,
        "password": hashed,
        "name": clean_name,
        "onboarded": False
    }
    
    # Save user
    db.users.insert_one(user_doc)
    SIGNUP_ATTEMPTS[client_ip].append(now)
    
    # Create profile document
    profile_doc = {
        "_id": str(uuid.uuid4()),
        "userId": user_id,
        "name": clean_name,
        "targetRole": "",
        "experienceLevel": "Student / Entry",
        "region": "",
        "expectedSalary": "",
        "skillsList": [],
        "careerScore": 0,
        "readinessScore": 0,
        "strengths": [],
        "weaknesses": [],
        "onboarded": False
    }
    db.profiles.insert_one(profile_doc)
    
    token = create_access_token({"sub": user_id, "email": clean_email})
    return {
        "token": token,
        "user": {"email": clean_email, "name": clean_name, "id": user_id, "onboarded": False}
    }

@app.post("/api/auth/login")
def login(data: LoginModel, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    clean_email = data.email.strip().lower()
    now = time.time()

    # Check brute force lockout on IP or email
    ip_attempts = [t for t in FAILED_LOGIN_ATTEMPTS[client_ip] if now - t < LOCKOUT_WINDOW_SECONDS]
    FAILED_LOGIN_ATTEMPTS[client_ip] = ip_attempts
    email_attempts = [t for t in FAILED_LOGIN_ATTEMPTS[clean_email] if now - t < LOCKOUT_WINDOW_SECONDS]
    FAILED_LOGIN_ATTEMPTS[clean_email] = email_attempts

    if len(ip_attempts) >= MAX_FAILED_ATTEMPTS or len(email_attempts) >= MAX_FAILED_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts. Account temporarily locked for 5 minutes for security."
        )

    user = db.users.find_one({"email": clean_email})

    # Constant-time verification to mitigate timing attacks
    password_valid = False
    if user and "password" in user:
        password_valid = verify_password(data.password, user["password"])
    else:
        # Dummy verification to equalize timing
        verify_password(data.password, DUMMY_HASH)

    if not user or not password_valid:
        FAILED_LOGIN_ATTEMPTS[client_ip].append(now)
        FAILED_LOGIN_ATTEMPTS[clean_email].append(now)
        raise HTTPException(status_code=400, detail="Invalid email or password.")

    # Successful login: reset failed attempts
    FAILED_LOGIN_ATTEMPTS[client_ip] = []
    FAILED_LOGIN_ATTEMPTS[clean_email] = []

    user_id = str(user.get("id") or user.get("_id"))
    token = create_access_token({"sub": user_id, "email": clean_email})

    # Check onboarded status
    user_onboarded = user.get("onboarded")
    if user_onboarded is None:
        prof = db.profiles.find_one({"userId": user_id})
        user_onboarded = bool(prof and prof.get("targetRole") and prof.get("skillsList"))

    return {
        "token": token,
        "user": {
            "email": clean_email,
            "name": user.get("name", "User"),
            "id": user_id,
            "onboarded": bool(user_onboarded)
        }
    }

# ==========================================
# ONBOARDING SYSTEM (MANDATORY GATE)
# ==========================================
@app.post("/api/onboarding/resume")
def onboarding_upload_resume(file: UploadFile = File(...), user: AuthUser = Depends(get_current_user)):
    file_id = str(uuid.uuid4())
    _, ext = os.path.splitext(file.filename.lower())
    
    if ext not in [".pdf", ".docx"]:
        raise HTTPException(status_code=400, detail="Please upload a valid PDF or DOCX resume document.")
        
    saved_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")
    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    size_bytes = os.path.getsize(saved_path)
    
    file_doc = {
        "_id": file_id,
        "id": file_id,
        "userId": user.id,
        "originalName": file.filename,
        "path": saved_path,
        "size": size_bytes,
        "category": "resume",
        "status": "processed",
        "createdAt": datetime.utcnow().isoformat()
    }
    db.files.insert_one(file_doc)
    
    # Extract text and parse with AI
    text = resume_parser.extract_text(saved_path, file.filename)
    parsed = resume_parser.structure_resume(text) if text else {
        "name": user.name or "Candidate",
        "target_role": "Data Scientist",
        "experience_level": "Student / Entry",
        "location": "Remote",
        "skills": ["Python", "SQL", "Problem Solving"]
    }
    
    extracted_skills = parsed.get("skills", [])
    suggested_role = parsed.get("target_role") or "Data Scientist"
    suggested_level = parsed.get("experience_level") or "Student / Entry"
    suggested_region = parsed.get("location") or "Remote"
    suggested_salary = "$80,000 - $120,000"
    
    db.profiles.update_one(
        {"userId": user.id},
        {
            "$set": {
                "skillsList": extracted_skills,
                "resumeFileId": file_id,
                "resumeFileName": file.filename
            }
        }
    )
    
    return {
        "fileId": file_id,
        "fileName": file.filename,
        "extracted": {
            "name": parsed.get("name") or user.name,
            "targetRole": suggested_role,
            "experienceLevel": suggested_level,
            "region": suggested_region,
            "expectedSalary": suggested_salary,
            "skills": extracted_skills
        }
    }

@app.post("/api/onboarding/complete")
def onboarding_complete(data: OnboardingCompleteModel, user: AuthUser = Depends(get_current_user)):
    target_role = data.targetRole.strip()
    experience_level = data.experienceLevel.strip()
    region = data.region.strip()
    expected_salary = data.expectedSalary.strip()
    
    if not target_role or not experience_level or not region or not expected_salary:
        raise HTTPException(
            status_code=400,
            detail="All 4 career parameters (Target Role, Experience Level, Preferred Region, Expected Salary Band) are compulsory."
        )
        
    # Verify that user has uploaded at least one resume file
    has_resume = db.files.find_one({"userId": user.id, "category": "resume"})
    if not has_resume:
        raise HTTPException(
            status_code=400,
            detail="A compulsory resume upload is required before completing onboarding."
        )
        
    # Update user document
    db.users.update_one(
        {"$or": [{"_id": user.id}, {"id": user.id}]},
        {"$set": {"onboarded": True}}
    )
    
    # Update profile document
    db.profiles.update_one(
        {"userId": user.id},
        {
            "$set": {
                "targetRole": target_role,
                "experienceLevel": experience_level,
                "region": region,
                "expectedSalary": expected_salary,
                "onboarded": True
            }
        }
    )
    
    # Generate insights and unlock initial achievements
    profile_engine.generate_profile_insights(user.id)
    ach_res = achievements.evaluate(user.id)
    
    updated_profile = db.profiles.find_one({"userId": user.id})
    updated_user = db.users.find_one({"$or": [{"_id": user.id}, {"id": user.id}]}) or {}
    
    return {
        "status": "success",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name or updated_user.get("name", "User"),
            "onboarded": True
        },
        "profile": updated_profile,
        "unlockedAchievements": ach_res.get("newly", [])
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
@app.get("/api/chat/conversations")
def list_conversations(user: AuthUser = Depends(get_current_user)):
    convs = db.conversations.find({"userId": user.id})
    convs_sorted = sorted(convs, key=lambda x: x.get("updatedAt", x.get("createdAt", "")), reverse=True)
    return {
        "conversations": [
            {
                "id": str(c.get("id") or c.get("_id")),
                "title": c.get("title", "New Conversation"),
                "createdAt": c.get("createdAt", ""),
                "updatedAt": c.get("updatedAt", "")
            }
            for c in convs_sorted
        ]
    }

@app.post("/api/chat/new")
def new_conversation(data: Optional[NewConversationModel] = None, user: AuthUser = Depends(get_current_user)):
    conv_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    raw_title = (data.title if data and data.title else "New Conversation").strip()
    title = raw_title[:40] if raw_title else "New Conversation"
    conv_doc = {
        "_id": conv_id,
        "id": conv_id,
        "userId": user.id,
        "title": title,
        "createdAt": now,
        "updatedAt": now
    }
    db.conversations.insert_one(conv_doc)
    return {
        "conversation": {
            "id": conv_id,
            "title": title,
            "createdAt": now,
            "updatedAt": now
        }
    }

@app.delete("/api/chat/conversations/{conv_id}")
def delete_conversation(conv_id: str, user: AuthUser = Depends(get_current_user)):
    db.conversations.delete_one({"userId": user.id, "id": conv_id})
    db.conversations.delete_one({"userId": user.id, "_id": conv_id})
    db.messages.delete_many({"userId": user.id, "conversationId": conv_id})
    return {"status": "ok", "deletedId": conv_id}

@app.get("/api/chat/history")
def chat_history(conversationId: Optional[str] = Query(None), user: AuthUser = Depends(get_current_user)):
    target_conv_id = conversationId
    if not target_conv_id:
        convs = db.conversations.find({"userId": user.id})
        convs_sorted = sorted(convs, key=lambda x: x.get("updatedAt", x.get("createdAt", "")), reverse=True)
        if convs_sorted:
            target_conv_id = str(convs_sorted[0].get("id") or convs_sorted[0].get("_id"))

    if not target_conv_id:
        return {"conversationId": None, "messages": []}

    msgs = db.messages.find({"userId": user.id, "conversationId": target_conv_id})
    msgs_sorted = sorted(msgs, key=lambda x: x.get("createdAt", ""))
    return {
        "conversationId": target_conv_id,
        "messages": [{"role": m["role"], "text": m["content"]} for m in msgs_sorted]
    }

@app.post("/api/chat")
def chat(data: ChatMessageModel, user: AuthUser = Depends(get_current_user)):
    now = datetime.utcnow().isoformat()
    clean_msg = data.message.strip()

    # 1. Retrieve or automatically create the conversation thread
    conv_id = data.conversationId
    conversation = None
    if conv_id:
        conversation = db.conversations.find_one({"userId": user.id, "_id": conv_id}) or db.conversations.find_one({"userId": user.id, "id": conv_id})

    if not conversation:
        conv_id = conv_id or str(uuid.uuid4())
        # Generate friendly title from first prompt (max 36 chars)
        derived_title = clean_msg.replace("\n", " ")[:36].strip()
        title = derived_title + ("..." if len(clean_msg) > 36 else "") if derived_title else "Career Guidance"
        conv_doc = {
            "_id": conv_id,
            "id": conv_id,
            "userId": user.id,
            "title": title,
            "createdAt": now,
            "updatedAt": now
        }
        db.conversations.insert_one(conv_doc)
    else:
        conv_id = str(conversation.get("id") or conversation.get("_id"))
        db.conversations.update_one(
            {"_id": conv_id},
            {"$set": {"updatedAt": now}}
        )

    # 2. Save user message to persistent DB
    user_msg_doc = {
        "_id": str(uuid.uuid4()),
        "userId": user.id,
        "conversationId": conv_id,
        "role": "user",
        "content": clean_msg,
        "createdAt": now
    }
    db.messages.insert_one(user_msg_doc)

    # 3. Sliding Window Memory Optimization:
    # We store all messages in MongoDB for full UI history, but only provide the last 8 messages
    # to Groq/LLM to prevent token bloat, latency spikes, and quota exhaustion!
    all_history = db.messages.find({"userId": user.id, "conversationId": conv_id})
    sorted_history = sorted(all_history, key=lambda x: x.get("createdAt", ""))
    recent_context = sorted_history[-8:]
    history = [{"role": m["role"], "content": m["content"]} for m in recent_context]

    # 4. Profile & Resume Context Injection
    profile = db.profiles.find_one({"userId": user.id}) or {}
    resume_files = list(db.files.find({"userId": user.id, "category": "resume"}))

    resume_context = ""
    if resume_files:
        try:
            latest_resume = sorted(resume_files, key=lambda x: x.get("createdAt", ""))[-1]
            raw_text = resume_parser.extract_text(latest_resume["path"], latest_resume["originalName"])
            resume_context = raw_text[:4000]
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

    # 5. Call LLM (Groq -> Gemini -> OpenAI -> Mock)
    res = llm_service.complete(system_prompt, history)
    bot_reply = res["text"]

    # 6. Save bot message to DB
    bot_msg_doc = {
        "_id": str(uuid.uuid4()),
        "userId": user.id,
        "conversationId": conv_id,
        "role": "bot",
        "content": bot_reply,
        "createdAt": datetime.utcnow().isoformat()
    }
    db.messages.insert_one(bot_msg_doc)

    # 7. Evaluate Achievements
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
