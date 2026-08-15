import os
import json
import re
import requests
from dotenv import load_dotenv
load_dotenv()

# Load environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Primary provider is Gemini if key exists, otherwise OpenAI or mock
if GEMINI_API_KEY:
    PROVIDER = "gemini"
elif OPENAI_API_KEY:
    PROVIDER = "openai"
else:
    PROVIDER = "mock (no keys configured)"

def complete(system: str, messages: list, max_tokens: int = 800, temperature: float = 0.4, json_mode: bool = False):
    """
    Calls the configured LLM API (Gemini or OpenAI) or returns a mock response if no keys exist.
    messages: list of dicts like [{"role": "user"|"assistant", "content": "text"}]
    """
    if PROVIDER == "gemini":
        return complete_gemini(system, messages, max_tokens, temperature, json_mode)
    elif PROVIDER == "openai":
        return complete_openai(system, messages, max_tokens, temperature, json_mode)
    else:
        return stub_response("Mock AI Response. Configure GEMINI_API_KEY or OPENAI_API_KEY in the environment to connect to a real model.", system, messages, json_mode)

def complete_gemini(system: str, messages: list, max_tokens: int, temperature: float, json_mode: bool):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        
        # Format conversation history
        contents = []
        for m in messages:
            role = "user" if m["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": m["content"]}]
            })
            
        payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system}]
            },
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"
            
        response = requests.post(url, json=payload, timeout=25)
        response.raise_for_status()
        data = response.json()
        
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return {"text": text, "stub": False, "raw": data}
        
    except Exception as e:
        print(f"[LLM Service - Gemini Error] {e}")
        return stub_response(f"Gemini API Error. Ensure your GEMINI_API_KEY is valid. Message: {str(e)}", system, messages, json_mode)

def complete_openai(system: str, messages: list, max_tokens: int, temperature: float, json_mode: bool):
    try:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        
        openai_messages = [{"role": "system", "content": system}]
        for m in messages:
            role = "user" if m["role"] == "user" else "assistant"
            openai_messages.append({"role": role, "content": m["content"]})
            
        payload = {
            "model": "gpt-4o-mini",
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
            
        response = requests.post(url, json=payload, headers=headers, timeout=25)
        response.raise_for_status()
        data = response.json()
        
        text = data["choices"][0]["message"]["content"]
        return {"text": text, "stub": False, "raw": data}
        
    except Exception as e:
        print(f"[LLM Service - OpenAI Error] {e}")
        return stub_response(f"OpenAI API Error. Ensure your OPENAI_API_KEY is valid. Message: {str(e)}", system, messages, json_mode)

def stub_response(warning_msg: str, system: str, messages: list, json_mode: bool):
    """
    Generates realistic offline mock data depending on the system prompt instruction
    so the app remains fully functional and testable without keys.
    """
    last_user_msg = ""
    for m in reversed(messages):
        if m["role"] == "user":
            last_user_msg = m["content"].lower()
            break
            
    if json_mode:
        # Detect what JSON format the system is asking for
        if "weeklyGoals" in system or "roadmap" in system:
            role = "Machine Learning Engineer"
            for r in ["data analyst", "ux designer", "product manager", "cloud/devops engineer", "cybersecurity analyst"]:
                if r in last_user_msg:
                    role = r.title()
                    
            mock_data = {
                "targetRole": role,
                "timelineMonths": 6,
                "weeklyGoals": [
                    "Week 1-2: Core Python syntax, data structures, and object-oriented programming.",
                    "Week 3-4: Advanced NumPy, Pandas vectorization, and data manipulation.",
                    "Week 5-6: Supervised Learning (Linear Regression, KNN, Decision Trees).",
                    "Week 7-8: Unsupervised Learning (K-Means, PCA) and Feature Engineering."
                ],
                "monthlyGoals": [
                    {"month": 1, "goal": "Master Python programming, Pandas, and basic mathematics (linear algebra)."},
                    {"month": 2, "goal": "Build 3 classic regression and classification models using scikit-learn."},
                    {"month": 3, "goal": "Complete a portfolio project analyzing a real Kaggle career dataset."}
                ],
                "courses": ["Intro to Machine Learning (Coursera/Fast.ai)", "Pandas & Python Data Science Handbook"],
                "projects": ["Kaggle Career Fit Predictor", "House Price Multi-Regression System"],
                "certifications": ["Google Data Analytics Professional Certificate"],
                "interviewPrep": ["Practice 15 coding questions on arrays & search", "Review Bayes Theorem and SVM math questions"],
                "portfolioIdeas": ["Create a GitHub repository showcasing hyperparameter tuning pipelines"]
            }
            return {"text": json.dumps(mock_data), "stub": True, "raw": None}
            
        elif "careerObjective" in system:
            mock_data = {
                "careerObjective": "Motivated ML enthusiast looking to design intelligent systems, optimize training pipelines, and bridge data science with backend software architectures.",
                "currentLevel": "Student / Entry",
                "strengths": ["Python scripting", "SQL & Relational Datasets", "Math fundamentals"],
                "weaknesses": ["Cloud pipelines", "Docker & Kubernetes scaling", "Deep learning libraries"]
            }
            return {"text": json.dumps(mock_data), "stub": True, "raw": None}
            
        elif "priorityOrder" in system: # Skill gap analysis
            mock_data = {
                "priorityOrder": ["Machine Learning Basics", "Feature Scaling", "Supervised Learning"],
                "items": [
                    {
                        "skill": "Machine Learning Basics",
                        "difficulty": "beginner",
                        "estimatedWeeks": 2,
                        "resources": ["Coursera ML Course by Andrew Ng", "StatQuest YouTube Series"]
                    },
                    {
                        "skill": "Feature Scaling",
                        "difficulty": "intermediate",
                        "estimatedWeeks": 1,
                        "resources": ["Scikit-Learn Preprocessing Documentation"]
                    }
                ]
            }
            return {"text": json.dumps(mock_data), "stub": True, "raw": None}
            
        elif "questions" in system: # Interview simulator questions
            mock_data = {
                "questions": [
                    "Explain the difference between supervised and unsupervised learning, and give an example of each.",
                    "What is the bias-variance tradeoff, and how does it relate to overfitting?",
                    "How does K-Nearest Neighbour (KNN) algorithm make predictions?",
                    "What evaluation metrics would you choose for an imbalanced classifier?",
                    "How do feature scaling and normalization impact algorithms like SVM or Gradient Descent?"
                ]
            }
            return {"text": json.dumps(mock_data), "stub": True, "raw": None}
            
        elif "score" in system: # Interview evaluation
            mock_data = {
                "score": 85,
                "feedback": "Great explanation! You accurately described the trade-off and gave proper details on model complexity.",
                "improvementSuggestions": [
                    "Mention specific techniques to handle variance, such as regularization or ensemble bagging.",
                    "Elaborate on how cross-validation acts as a check for generalization."
                ]
            }
            return {"text": json.dumps(mock_data), "stub": True, "raw": None}
            
        else:
            return {"text": json.dumps({"note": warning_msg}), "stub": True, "raw": None}
            
    else:
        # Standard chat fallback
        bot_response = f"**{warning_msg}**\n\nHere is some career advice offline:\n\n* **To enter Machine Learning:** Focus on Python, statistics, linear algebra, and training supervised classifiers (like Logistic Regression, SVM, KNN, Random Forest) on datasets. Learn to scale features using StandardScaler.\n* **To enter Data Analytics:** Focus on SQL query optimization, data visualization (Matplotlib, Tableau), and descriptive statistics.\n* **To enter DevOps:** Learn Linux commands, Docker containerization, Git workflows, and Cloud deployment configurations.\n\nTell me about your target job and we can mock a roadmap!"
        
        # Simple RAG-lite response for specific terms
        if "data science" in last_user_msg or "machine learning" in last_user_msg:
            bot_response = f"**{warning_msg}**\n\nTo start with **Machine Learning**, you need to cover these core steps:\n1. Learn **Supervised learning** models like Decision Trees, SVM, and KNN.\n2. Master **Feature scaling** (normalization vs standardization).\n3. Understand **bias/variance tradeoff** to control overfitting.\n4. Practice on real tabular datasets (like Kaggle)."
        elif "product" in last_user_msg:
            bot_response = f"**{warning_msg}**\n\nFor **Product Management**, you need to mix communication skills with technical basics. Focus on agile workflows, product metrics, and database fundamentals (SQL)."

        return {"text": bot_response, "stub": True, "raw": None}

def complete_json(system: str, messages: list, max_tokens: int = 800, temperature: float = 0.4):
    """Convenience helper to enforce JSON mode and parse the resulting JSON string safely."""
    res = complete(system, messages, max_tokens, temperature, json_mode=True)
    text = res["text"]
    stub = res["stub"]
    
    if stub:
        try:
            return {"data": json.loads(text), "stub": True, "text": text}
        except Exception:
            return {"data": None, "stub": True, "text": text}
            
    # Clean output backticks if model returned prose
    cleaned = re.sub(r"```json", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"```", "", cleaned).strip()
    
    try:
        return {"data": json.loads(cleaned), "stub": False, "text": text}
    except Exception as e:
        print(f"[LLM Service] JSON parse failure on text: {cleaned}. Error: {e}")
        # Try a regex regex extraction of json block
        match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", cleaned)
        if match:
            try:
                return {"data": json.loads(match.group(0)), "stub": False, "text": text}
            except Exception:
                pass
        return {"data": None, "stub": False, "text": text}
