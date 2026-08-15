import os
import re
from pypdf import PdfReader
import docx
from services.llm_service import complete_json

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-().]{8,}\d)")

def extract_text(file_path: str, original_name: str) -> str:
    """Extracts raw text from an uploaded file based on its extension."""
    _, ext = os.path.splitext(original_name.lower())
    
    if ext == ".pdf":
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        except Exception as e:
            print(f"[ResumeParser] PDF extraction error: {e}")
            return ""
            
    elif ext == ".docx":
        try:
            doc = docx.Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
            return text
        except Exception as e:
            print(f"[ResumeParser] DOCX extraction error: {e}")
            return ""
            
    elif ext in [".png", ".jpg", ".jpeg"]:
        # Photographic images are supported for upload but not OCR'd in this build
        return ""
        
    return ""

def quick_regex_fields(text: str) -> dict:
    """Quick regex extraction of email, phone, and possible name from text."""
    email_match = EMAIL_RE.search(text)
    phone_match = PHONE_RE.search(text)
    
    email = email_match.group(0) if email_match else None
    phone = phone_match.group(0) if phone_match else None
    
    # Estimate name from the first non-empty line of text
    first_line = None
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if lines:
        first_line = lines[0]
        
    return {
        "email": email,
        "phone": phone,
        "possibleName": first_line
    }

def structure_resume(raw_text: str) -> dict:
    """
    Transforms raw resume text into a structured profile dictionary.
    Uses the LLM service or falls back to regex-only if no API keys are present.
    """
    quick = quick_regex_fields(raw_text)
    
    system_prompt = (
        "You extract structured data from resumes. Respond with ONLY valid JSON, no prose, no markdown fences. "
        "If a field isn't present in the resume, use null or an empty array. Never invent information that isn't in the text."
    )
    
    schema = """{
  "name": string|null,
  "email": string|null,
  "phone": string|null,
  "education": [{"degree": string, "institution": string, "year": string|null}],
  "experience": [{"title": string, "company": string, "duration": string|null, "highlights": [string]}],
  "projects": [{"name": string, "description": string}],
  "certifications": [string],
  "skills": [string],
  "languages": [string],
  "tools": [string],
  "frameworks": [string],
  "soft_skills": [string],
  "achievements": [string]
}"""

    # Slice raw text to prevent token blowing
    truncated_text = raw_text[:12000]
    
    user_prompt = f"Extract fields matching this JSON schema exactly:\n{schema}\n\nResume text:\n\"\"\"\n{truncated_text}\n\"\"\""
    
    res = complete_json(system_prompt, [{"role": "user", "content": user_prompt}])
    data = res["data"]
    stub = res["stub"]
    
    if stub or not data:
        # Fallback for offline mode
        # Extract some mock skills if we find keywords
        found_skills = []
        lower_text = raw_text.lower()
        skills_keywords = [
            "python", "machine learning", "ml", "sql", "java", "react", "html", "css", "figma",
            "javascript", "c++", "pytorch", "tensorflow", "statistics", "data science", "cloud",
            "kubernetes", "docker", "aws", "git", "communication", "product management", "linux"
        ]
        for kw in skills_keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", lower_text):
                found_skills.append(kw.title() if kw != "ml" and kw != "sql" and kw != "aws" else kw.upper())
                
        # Clean duplicates
        found_skills = list(set(found_skills))
        
        return {
            "name": quick["possibleName"] or "Guest Explorer",
            "email": quick["email"],
            "phone": quick["phone"],
            "education": [],
            "experience": [],
            "projects": [],
            "certifications": [],
            "skills": found_skills or ["Python", "SQL", "Communication"],
            "languages": [],
            "tools": [],
            "frameworks": [],
            "soft_skills": [],
            "achievements": [],
            "_extractionMode": "regex-fallback"
        }
        
    return {
        "name": data.get("name") or quick["possibleName"] or "Guest Explorer",
        "email": data.get("email") or quick["email"],
        "phone": data.get("phone") or quick["phone"],
        "education": data.get("education") or [],
        "experience": data.get("experience") or [],
        "projects": data.get("projects") or [],
        "certifications": data.get("certifications") or [],
        "skills": data.get("skills") or [],
        "languages": data.get("languages") or [],
        "tools": data.get("tools") or [],
        "frameworks": data.get("frameworks") or [],
        "soft_skills": data.get("soft_skills") or [],
        "achievements": data.get("achievements") or [],
        "_extractionMode": "ai"
    }
