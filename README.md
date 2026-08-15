# Kingmaker — AI Career Intelligence Platform

Kingmaker is a full-stack Career Intelligence and Guidance platform built with a **Python FastAPI backend**, **Vite + React frontend**, and **MongoDB database** (with automatic local JSON file fallback).

It integrates a comprehensive **Machine Learning Laboratory Sandbox** showcasing a complete list of 13+ ML syllabus algorithms and core theoretical concepts.

---

## Architecture & Stack

- **Frontend:** React (Vite, HSL CSS design system, SVG icons)
- **Backend:** Python FastAPI (Uvicorn server, JWT authentication)
- **Database:** MongoDB (using `pymongo` with automatic local JSON-based persistence fallback)
- **Machine Learning Engine:** Scikit-Learn, Pandas, NumPy (all running locally and offline)
- **AI Guidance Engine:** Google Gemini API (with simulated offline Mock AI fallback)

---

## Getting Started

### 1. Prerequisites
Ensure you have **Python 3.8+** and **Node.js 16+** installed on your system.

---

### 2. Backend Setup
1. Open a terminal in the `backend/` directory:
   ```bash
   cd backend
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. (Optional) Set your Gemini API key as an environment variable to activate real AI guidance (otherwise the app will run with a simulated Mock AI service offline):
   ```bash
   # On Windows (cmd)
   set GEMINI_API_KEY=your_key_here
   
   # On Windows (PowerShell)
   $env:GEMINI_API_KEY="your_key_here"
   ```
4. Start the FastAPI server:
   ```bash
   python main.py
   ```
   The backend server will launch on [http://localhost:8000](http://localhost:8000).

---

### 3. Frontend Setup
1. Open a new terminal in the `frontend/` directory:
   ```bash
   cd frontend
   ```
2. Install Node packages:
   ```bash
   npm install
   ```
3. Start the Vite React development server:
   ```bash
   npm run dev
   ```
   The frontend dashboard will run on [http://localhost:5173](http://localhost:5173).

---

## Features Walkthrough

### 💬 Guidance Bot (RAG-Lite Chat)
* Ask career guidance questions (e.g. *"What skills do I need to become an ML Engineer?"*).
* Returns structured guidance based on your skill levels.

### 📁 Upload Files (Resume Parser)
* Upload a PDF or DOCX resume. 
* The backend extracts text, scans for technical skills (Python, SQL, ML, etc.), updates your profile, and unlocks achievements.

### 👤 Profile View
* View your current readiness score and target career title.
* Edit target criteria (Expected salary, Region) and see your skill profile matrix update.

### 🧭 Personalized Roadmaps
* Request a timeline-based roadmap for any career path.
* Generates weekly/monthly objectives, recommended courses, and projects.

### 🔬 ML Lab & Dataset Explorer (Interactive Sandbox)
1. **Kaggle Dataset Explorer:** Inspect statistics, descriptions, and previews of the synthetic `career_data.csv` dataset.
2. **Classifier Arena:** Tune parameters and train models:
   * *Algorithms:* Logistic Regression, SVM, KNN, Decision Tree, Random Forest, Naive Bayes, Perceptron, Bagging, Boosting.
   * *Preprocessing:* StandardScaler, MinMaxScaler, split-ratio tuning.
   * *Outputs:* Accuracy, Precision, Recall, F1-score, and Cross-Validation scores.
3. **Salary Regressor Sandbox:** Train regressors (Simple, Multiple, Polynomial, Bayesian Linear Regression) to predict salary and monitor MSE/RMSE.
4. **K-Means Skill Clustering:** Group candidates into $K$ skill-set archetypes (e.g., Tech Specialist, Creative Designer, Leader).
5. **Theory Guide:** Review explanations for bias/variance, inductive bias, supervised/unsupervised learning, and gradient descent.

### 🏆 Achievements & Gamification
* Tracks user progression (First Upload, First Chat, Path Finder, Certified) and unlocks gamified badges.