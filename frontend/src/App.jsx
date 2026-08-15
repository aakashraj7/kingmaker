import React, { useState, useEffect, useRef } from "react";

const API_BASE = "http://localhost:8000";

export default function App() {
  // ---- Auth States ----
  const [token, setToken] = useState(localStorage.getItem("kmk_token") || "");
  const [guestId, setGuestId] = useState(localStorage.getItem("kmk_guest_id") || "");
  const [user, setUser] = useState(JSON.parse(localStorage.getItem("kmk_user") || "null"));
  const [authMode, setAuthMode] = useState("login");
  const [authName, setAuthName] = useState("");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authError, setAuthError] = useState("");

  // ---- Navigation ----
  const [view, setView] = useState("chat");

  // ---- Core Feature States ----
  const [chatMessages, setChatMessages] = useState([
    { role: "bot", text: "Hi, I'm the Kingmaker guidance bot. Tell me about your background, or ask a question — e.g. \"What skills do I need for data science?\"" }
  ]);
  const [chatInput, setChatInput] = useState("");
  const [chatConversationId, setChatConversationId] = useState(null);
  const [chatThinking, setChatThinking] = useState(false);

  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);

  const [market, setMarket] = useState(null);
  const [loadingMarket, setLoadingMarket] = useState(false);

  const [roadmaps, setRoadmaps] = useState([]);
  const [roadmapInput, setRoadmapInput] = useState("");
  const [selectedRoadmap, setSelectedRoadmap] = useState(null);
  const [generatingRoadmap, setGeneratingRoadmap] = useState(false);

  const [profile, setProfile] = useState(null);
  const [editingProfile, setEditingProfile] = useState(false);

  const [achievements, setAchievements] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [loadingDashboard, setLoadingDashboard] = useState(false);

  // ---- Settings ----
  const [settings, setSettings] = useState({ theme: "dark", notificationsEnabled: true, preferredAIModel: "mock" });
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);

  // ---- ML Lab Sandbox States ----
  const [mlTab, setMlTab] = useState("dataset");
  const [datasetData, setDatasetData] = useState(null);
  const [loadingDataset, setLoadingDataset] = useState(false);
  const [modelComparisons, setModelComparisons] = useState([]);
  const [loadingComparisons, setLoadingComparisons] = useState(false);

  // Classifier Sandbox
  const [selectedClassifier, setSelectedClassifier] = useState("random_forest");
  const [clfSplit, setClfSplit] = useState(0.2);
  const [clfScaling, setClfScaling] = useState("standard");
  const [clfParams, setClfParams] = useState({
    n_estimators: 50,
    max_depth: 5,
    n_neighbors: 5,
    C: 1.0,
    eta0: 1.0
  });
  const [clfMetrics, setClfMetrics] = useState(null);
  const [trainingClassifier, setTrainingClassifier] = useState(false);

  // Regressor Sandbox
  const [selectedRegressor, setSelectedRegressor] = useState("multiple_linear");
  const [regSplit, setRegSplit] = useState(0.2);
  const [regScaling, setRegScaling] = useState("none");
  const [regParams, setRegParams] = useState({ degree: 2 });
  const [regMetrics, setRegMetrics] = useState(null);
  const [trainingRegressor, setTrainingRegressor] = useState(false);

  // Clustering Sandbox
  const [clusterK, setClusterK] = useState(3);
  const [clusterResults, setClusterResults] = useState([]);
  const [runningClustering, setRunningClustering] = useState(false);

  const messagesEndRef = useRef(null);

  // ---- API Helper ----
  const api = async (path, options = {}) => {
    const headers = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    else if (guestId) headers["x-guest-id"] = guestId;

    if (!options.isForm && options.body) {
      headers["Content-Type"] = "application/json";
    }

    const res = await fetch(`${API_BASE}${path}`, {
      method: options.method || "GET",
      headers,
      body: options.isForm ? options.body : options.body ? JSON.stringify(options.body) : undefined,
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || `Request failed (${res.status})`);
    }
    return data;
  };

  // ---- Effects ----
  useEffect(() => {
    if (token || guestId) {
      fetchDashboard();
      fetchProfile();
      fetchFiles();
      fetchRoadmaps();
      fetchAchievements();
      fetchSettings();
    }
  }, [token, guestId]);

  useEffect(() => {
    if (view === "market") {
      fetchMarket();
    } else if (view === "ml_lab") {
      fetchMLData();
    }
  }, [view]);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatMessages, chatThinking]);

  // ---- Fetch Functions ----
  const fetchDashboard = async () => {
    setLoadingDashboard(true);
    try {
      const data = await api("/api/tools/dashboard");
      setDashboard(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingDashboard(false);
    }
  };

  const fetchProfile = async () => {
    try {
      const data = await api("/api/profile");
      setProfile(data.profile);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchFiles = async () => {
    try {
      const data = await api("/api/upload");
      setFiles(data.files);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchRoadmaps = async () => {
    try {
      const data = await api("/api/roadmap");
      setRoadmaps(data.roadmaps);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchAchievements = async () => {
    try {
      const data = await api("/api/tools/achievements");
      setAchievements(data.achievements);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchSettings = async () => {
    try {
      const data = await api("/api/tools/settings");
      setSettings(data);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchMarket = async () => {
    setLoadingMarket(true);
    try {
      const data = await api("/api/market");
      setMarket(data.market);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingMarket(false);
    }
  };

  const fetchMLData = async () => {
    if (mlTab === "dataset" && !datasetData) {
      setLoadingDataset(true);
      try {
        const data = await api("/api/ml/dataset");
        setDatasetData(data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoadingDataset(false);
      }
    } else if (mlTab === "classifiers" && modelComparisons.length === 0) {
      setLoadingComparisons(true);
      try {
        const data = await api("/api/ml/compare");
        setModelComparisons(data.comparison);
      } catch (e) {
        console.error(e);
      } finally {
        setLoadingComparisons(false);
      }
    }
  };

  useEffect(() => {
    fetchMLData();
  }, [mlTab]);

  // ---- Auth Handlers ----
  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthError("");
    const path = authMode === "signup" ? "/api/auth/signup" : "/api/auth/login";
    const body = authMode === "signup"
      ? { email: authEmail, password: authPassword, name: authName }
      : { email: authEmail, password: authPassword };

    try {
      const data = await api(path, { method: "POST", body });
      localStorage.setItem("kmk_token", data.token);
      localStorage.setItem("kmk_user", JSON.stringify(data.user));
      setToken(data.token);
      setUser(data.user);
      setView("chat");
    } catch (err) {
      setAuthError(err.message);
    }
  };

  const handleGuestLogin = async () => {
    setAuthError("");
    try {
      const data = await api("/api/auth/guest", { method: "POST" });
      localStorage.setItem("kmk_guest_id", data.guestId);
      setGuestId(data.guestId);
      setUser({ name: "Guest Explorer", email: "" });
      setView("chat");
    } catch (err) {
      setAuthError(err.message);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("kmk_token");
    localStorage.removeItem("kmk_guest_id");
    localStorage.removeItem("kmk_user");
    setToken("");
    setGuestId("");
    setUser(null);
  };

  // ---- Action Handlers ----
  const handleSendMessage = async (text) => {
    if (!text.trim()) return;
    const cleanMsg = text.trim();
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", text: cleanMsg }]);
    setChatThinking(true);

    try {
      const data = await api("/api/chat", {
        method: "POST",
        body: { message: cleanMsg, conversationId: chatConversationId }
      });
      setChatConversationId(data.conversationId);
      setChatMessages((prev) => [...prev, { role: "bot", text: data.reply }]);
      if (data.unlockedAchievements?.length) {
        showToasts(data.unlockedAchievements);
        fetchAchievements();
      }
      fetchDashboard();
    } catch (e) {
      setChatMessages((prev) => [...prev, { role: "bot", text: `I am having trouble: ${e.message}` }]);
    } finally {
      setChatThinking(false);
    }
  };

  const handleFileUpload = async (e) => {
    const filesUploaded = e.target.files;
    if (!filesUploaded || filesUploaded.length === 0) return;
    setUploading(true);

    try {
      for (let i = 0; i < filesUploaded.length; i++) {
        const formData = new FormData();
        formData.append("file", filesUploaded[i]);
        const data = await api("/api/upload", {
          method: "POST",
          body: formData,
          isForm: true
        });
        if (data.unlockedAchievements?.length) {
          showToasts(data.unlockedAchievements);
          fetchAchievements();
        }
      }
      fetchFiles();
      fetchProfile();
      fetchDashboard();
    } catch (err) {
      alert(`File upload failed: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteFile = async (id) => {
    try {
      await api(`/api/upload/${id}`, { method: "DELETE" });
      fetchFiles();
      fetchDashboard();
    } catch (e) {
      alert(e.message);
    }
  };

  const handleGenerateRoadmap = async () => {
    if (!roadmapInput.trim()) return;
    setGeneratingRoadmap(true);
    try {
      const data = await api("/api/roadmap", {
        method: "POST",
        body: { targetRole: roadmapInput }
      });
      setRoadmapInput("");
      setRoadmaps((prev) => [data.roadmap, ...prev]);
      setSelectedRoadmap(data.roadmap);
      if (data.unlockedAchievements?.length) {
        showToasts(data.unlockedAchievements);
        fetchAchievements();
      }
      fetchDashboard();
    } catch (e) {
      alert(e.message);
    } finally {
      setGeneratingRoadmap(false);
    }
  };

  const handleSaveProfile = async () => {
    try {
      const data = await api("/api/profile", {
        method: "PUT",
        body: {
          targetRole: profile.targetRole,
          experienceLevel: profile.experienceLevel,
          region: profile.region,
          expectedSalary: profile.expectedSalary
        }
      });
      setProfile(data.profile);
      setEditingProfile(false);
      fetchDashboard();
      if (data.unlockedAchievements?.length) {
        showToasts(data.unlockedAchievements);
        fetchAchievements();
      }
    } catch (e) {
      alert(e.message);
    }
  };

  const handleSaveSettings = async (checked) => {
    try {
      const data = await api("/api/tools/settings", {
        method: "PUT",
        body: { notificationsEnabled: checked }
      });
      setSettings(data.settings);
    } catch (e) {
      console.error(e);
    }
  };

  // ---- ML Lab Sandboxes ----
  const handleTrainClassifier = async () => {
    setTrainingClassifier(true);
    try {
      const data = await api("/api/ml/train/classifier", {
        method: "POST",
        body: {
          modelName: selectedClassifier,
          testSize: parseFloat(clfSplit),
          scaling: clfScaling,
          params: clfParams
        }
      });
      setClfMetrics(data);
    } catch (e) {
      alert(e.message);
    } finally {
      setTrainingClassifier(false);
    }
  };

  const handleTrainRegressor = async () => {
    setTrainingRegressor(true);
    try {
      const data = await api("/api/ml/train/regressor", {
        method: "POST",
        body: {
          modelName: selectedRegressor,
          testSize: parseFloat(regSplit),
          scaling: regScaling,
          params: regParams
        }
      });
      setRegMetrics(data);
    } catch (e) {
      alert(e.message);
    } finally {
      setTrainingRegressor(false);
    }
  };

  const handleRunClustering = async () => {
    setRunningClustering(true);
    try {
      const data = await api(`/api/ml/cluster?nClusters=${clusterK}`, {
        method: "POST"
      });
      setClusterResults(data.clusters);
    } catch (e) {
      alert(e.message);
    } finally {
      setRunningClustering(false);
    }
  };

  // Toast System
  const [toasts, setToasts] = useState([]);
  const showToasts = (unlocked) => {
    unlocked.forEach((a) => {
      const id = Math.random();
      setToasts((prev) => [...prev, { id, name: a.name, icon: a.icon || "🏆" }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 4000);
    });
  };

  // ---- Auth Gate ----
  if (!token && !guestId) {
    return (
      <div className="kmk-auth-wrap" style={{ margin: "12vh auto" }}>
        <div className="kmk-auth-brand">
          <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
            <path d="M13 3C9 3 8 8 8 11C8 15 10 17 13 17C16 17 18 15 18 11C18 8 17 3 13 3Z" stroke="#e8c368" strokeWidth="1.4" />
            <path d="M13 3V17" stroke="#e8c368" strokeWidth="1.2" />
            <path d="M8 20L13 17L18 20" stroke="#2a9d8f" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
          <div className="txt">KINGMAKER</div>
        </div>

        <div className="kmk-auth-tabs">
          <div className={`kmk-auth-tab ${authMode === "login" ? "active" : ""}`} onClick={() => setAuthMode("login")}>Log In</div>
          <div className={`kmk-auth-tab ${authMode === "signup" ? "active" : ""}`} onClick={() => setAuthMode("signup")}>Sign Up</div>
        </div>

        <form onSubmit={handleAuthSubmit}>
          {authMode === "signup" && (
            <div className="kmk-auth-field">
              <label>Name</label>
              <input type="text" value={authName} onChange={(e) => setAuthName(e.target.value)} placeholder="Jane Doe" required />
            </div>
          )}
          <div className="kmk-auth-field">
            <label>Email</label>
            <input type="email" value={authEmail} onChange={(e) => setAuthEmail(e.target.value)} placeholder="you@example.com" required />
          </div>
          <div className="kmk-auth-field">
            <label>Password</label>
            <input type="password" value={authPassword} onChange={(e) => setAuthPassword(e.target.value)} placeholder="At least 8 characters" required />
          </div>
          <button type="submit" className="kmk-auth-submit">
            {authMode === "signup" ? "Sign Up" : "Log In"}
          </button>
          {authError && <div className="kmk-auth-error">{authError}</div>}
        </form>

        <button className="kmk-auth-guest" onClick={handleGuestLogin}>Continue as Guest</button>
        <div className="kmk-auth-foot">Offline Sandbox. React + MongoDB Stack</div>
      </div>
    );
  }

  return (
    <div className="kmk-root">
      {/* Toast Render */}
      <div style={{ position: "fixed", bottom: 20, right: 20, zIndex: 999, display: "flex", flexDirection: "column", gap: 10 }}>
        {toasts.map((t) => (
          <div key={t.id} style={{ background: "#12332e", color: "#3ec6b5", border: "1px solid #1e5147", padding: "10px 16px", borderRadius: 10, fontSize: "12.5px", boxShadow: "0 6px 20px rgba(0,0,0,.3)" }}>
            {t.icon} Achievement unlocked: {t.name}
          </div>
        ))}
      </div>

      {/* SIDEBAR */}
      <div className="kmk-side">
        <div className="kmk-brand">
          <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
            <path d="M13 3C9 3 8 8 8 11C8 15 10 17 13 17C16 17 18 15 18 11C18 8 17 3 13 3Z" stroke="#e8c368" strokeWidth="1.4" />
            <path d="M13 3V17" stroke="#e8c368" strokeWidth="1.2" />
            <path d="M8 20L13 17L18 20" stroke="#2a9d8f" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
          <div>
            <div className="kmk-brand-text">KINGMAKER</div>
            <div className="kmk-brand-sub">Career Intelligence</div>
          </div>
        </div>
        
        <div className="kmk-nav">
          <button className={`kmk-nav-btn ${view === "chat" ? "active" : ""}`} onClick={() => setView("chat")}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" strokeWidth="2"><path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" /></svg>
            <span className="label">Guidance Bot</span>
          </button>
          
          <button className={`kmk-nav-btn ${view === "upload" ? "active" : ""}`} onClick={() => setView("upload")}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
            <span className="label">Upload Files</span>
          </button>
          
          <button className={`kmk-nav-btn ${view === "market" ? "active" : ""}`} onClick={() => setView("market")}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" strokeWidth="2"><path d="M3 3v18h18" /><path d="M18.7 8l-5.1 5.1-2.8-2.8L7 14" /></svg>
            <span className="label">Market View</span>
          </button>
          
          <button className={`kmk-nav-btn ${view === "roadmap" ? "active" : ""}`} onClick={() => setView("roadmap")}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" strokeWidth="2"><path d="M9 20l-5-2V6l5 2 6-2 5 2v14l-5-2-6 2z" /><path d="M9 8v14" /><path d="M15 6v14" /></svg>
            <span className="label">Roadmap</span>
          </button>

          <button className={`kmk-nav-btn ${view === "profile" ? "active" : ""}`} onClick={() => setView("profile")}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
            <span className="label">Profile</span>
          </button>

          <button className={`kmk-nav-btn ${view === "achievements" ? "active" : ""}`} onClick={() => setView("achievements")}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" strokeWidth="2"><circle cx="12" cy="8" r="6" /><path d="M8.7 13.6 7 22l5-3 5 3-1.7-8.4" /></svg>
            <span className="label">Achievements</span>
          </button>

          <button className={`kmk-nav-btn ${view === "dashboard" ? "active" : ""}`} onClick={() => setView("dashboard")}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" strokeWidth="2"><rect x="3" y="3" width="7" height="9" /><rect x="14" y="3" width="7" height="5" /><rect x="14" y="12" width="7" height="9" /><rect x="3" y="16" width="7" height="5" /></svg>
            <span className="label">Dashboard</span>
          </button>

          <button className={`kmk-nav-btn ${view === "ml_lab" ? "active" : ""}`} onClick={() => setView("ml_lab")}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" strokeWidth="2" stroke="currentColor"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>
            <span className="label" style={{ fontWeight: 600, color: "var(--gold)" }}>ML Lab & Dataset</span>
          </button>
        </div>

        <div className="kmk-side-foot">
          Level 3 Pipeline<br /><b>ML Sandbox</b> · Active
        </div>
      </div>

      {/* MAIN CONTAINER */}
      <div className="kmk-main">
        <div className="kmk-topbar">
          <div>
            <h1>
              {view === "chat" && "Guidance Bot"}
              {view === "upload" && "Upload Files"}
              {view === "market" && "Market Snapshot"}
              {view === "roadmap" && "Personalized Roadmaps"}
              {view === "profile" && "Career Profile"}
              {view === "achievements" && "Gamified Achievements"}
              {view === "dashboard" && "Career Twin Dashboard"}
              {view === "ml_lab" && "Machine Learning & Dataset Laboratory"}
            </h1>
            <p>
              {view === "chat" && "Ask about career planning, machine learning topics, or job signals"}
              {view === "upload" && "Upload your resume or certificates to update your profile"}
              {view === "market" && "Drifting job metrics based on actual market indicators"}
              {view === "roadmap" && "Construct a weekly study guide for any industry path"}
              {view === "profile" && "Examine your strengths, scores, and skills coverage"}
              {view === "achievements" && "Milestones representing your progression"}
              {view === "dashboard" && "View details relating to career metrics and scores"}
              {view === "ml_lab" && "Interactive sandbox with 13+ ML models, scaling, and datasets"}
            </p>
          </div>
          <div className="kmk-topbar-user">
            <div className="kmk-pill">
              <span className="dot"></span> Local Server Active
            </div>
            <button className="kmk-logout" onClick={() => setSettingsModalOpen(true)}>Settings</button>
            <button className="kmk-logout" onClick={handleLogout}>Log Out</button>
          </div>
        </div>

        <div className="kmk-view">
          {/* VIEW: CHAT */}
          {view === "chat" && (
            <div className="kmk-chat-wrap">
              <div className="kmk-messages">
                {chatMessages.map((m, i) => (
                  <div key={i} className={`kmk-msg ${m.role === "bot" ? "bot" : "user"}`}>
                    <div dangerouslySetInnerHTML={{
                      __html: m.text
                        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                        .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
                        .replace(/\n/g, "<br />")
                    }} />
                  </div>
                ))}
                {chatThinking && (
                  <div className="kmk-typing">
                    <span></span><span></span><span></span>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              <div className="kmk-suggest-row">
                <div className="kmk-suggest" onClick={() => handleSendMessage("What careers suit someone who likes machine learning?")}>ML Careers</div>
                <div className="kmk-suggest" onClick={() => handleSendMessage("What is the bias variance trade-off in machine learning?")}>Bias & Variance</div>
                <div className="kmk-suggest" onClick={() => handleSendMessage("How does K-Nearest Neighbour classification work?")}>How KNN works</div>
              </div>

              <div className="kmk-input-row">
                <textarea
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Ask a career question or request ML concepts explanation..."
                  rows="2"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage(chatInput);
                    }
                  }}
                />
                <button className="kmk-send" onClick={() => handleSendMessage(chatInput)} disabled={!chatInput.trim() || chatThinking}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1a1200" strokeWidth="2.3">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </button>
              </div>
            </div>
          )}

          {/* VIEW: UPLOAD */}
          {view === "upload" && (
            <div>
              <div className="kmk-drop" onClick={() => document.getElementById("file-picker").click()}>
                <svg width="34" height="34" viewBox="0 0 24 24" fill="none" strokeWidth="1.6"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
                <h3>{uploading ? "Uploading and processing file..." : "Click to upload a document"}</h3>
                <p>PDF or DOCX resumes and certificates (Up to 10MB)</p>
                <input type="file" id="file-picker" style={{ display: "none" }} onChange={handleFileUpload} accept=".pdf,.docx,.png,.jpg,.jpeg" multiple />
              </div>

              <div className="kmk-section-title"><span className="bar"></span>Uploaded Artifacts</div>
              <div className="kmk-file-list">
                {files.length === 0 ? (
                  <div className="kmk-empty-note">No documents uploaded yet. Upload a resume to scan for skills!</div>
                ) : (
                  files.map((f) => (
                    <div key={f.id} className="kmk-file-row">
                      <div className="kmk-file-icon">{f.name.split(".").pop().toUpperCase().slice(0, 4)}</div>
                      <div className="kmk-file-meta">
                        <div className="kmk-file-name">{f.name}</div>
                        <div className="kmk-file-sub">{Math.round(f.size / 1024)} KB · Completed</div>
                      </div>
                      <span className="kmk-file-tag">{f.category || "document"}</span>
                      <button className="kmk-file-x" onClick={() => handleDeleteFile(f.id)}>✕</button>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* VIEW: MARKET */}
          {view === "market" && (
            <div>
              {loadingMarket ? (
                <div className="kmk-loading-msg">Fetching live demand signals...</div>
              ) : market ? (
                <div>
                  <div className="kmk-grid">
                    <div className="kmk-card"><h4>Active Job Signals</h4><div className="big">{market.summary.activeJobSignals}</div><div className="trend up">▲ 6.4% this cycle</div></div>
                    <div className="kmk-card"><h4>Avg. Entry Salary</h4><div className="big">{market.summary.avgEntrySalary}</div><div className="trend up">▲ 3.2% YoY</div></div>
                    <div className="kmk-card"><h4>Automation Risk</h4><div className="big">{market.summary.automationRiskAvg}</div><div className="trend down">▼ low probability</div></div>
                    <div className="kmk-card"><h4>Skill Gap Alerts</h4><div className="big">{market.summary.skillGapAlerts}</div><div className="trend up">active targets</div></div>
                  </div>

                  <div className="kmk-section-title"><span className="bar"></span>Top Roles in Demand</div>
                  <div>
                    {market.topRoles.map((r, i) => (
                      <div key={i} className="kmk-role-row">
                        <div className="kmk-role-rank">#{r.rank}</div>
                        <div className="kmk-role-name" style={{ fontWeight: 600 }}>{r.name}</div>
                        <div className="kmk-role-bar-track">
                          <div className="kmk-role-bar-fill" style={{ width: `${r.demandScore}%` }} />
                        </div>
                        <div className="kmk-role-pct">{r.demandScore}%</div>
                        <div style={{ fontSize: "11px", color: "var(--teal-bright)", width: 44, textAlign: "right" }}>{r.trend}</div>
                      </div>
                    ))}
                  </div>

                  <div className="kmk-section-title"><span className="bar"></span>NLP Extracted Trending Skills</div>
                  <div className="kmk-suggest-row">
                    {market.trendingSkills.map((s, i) => (
                      <div key={i} className="kmk-suggest">{s}</div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="kmk-error-msg">Failed to load market snapshot.</div>
              )}
            </div>
          )}

          {/* VIEW: ROADMAP */}
          {view === "roadmap" && (
            <div>
              <div className="kmk-roadmap-form">
                <input
                  type="text"
                  value={roadmapInput}
                  onChange={(e) => setRoadmapInput(e.target.value)}
                  placeholder="Enter target career field (e.g., Machine Learning Engineer)..."
                />
                <button onClick={handleGenerateRoadmap} disabled={generatingRoadmap || !roadmapInput.trim()}>
                  {generatingRoadmap ? "Generating..." : "Create Roadmap"}
                </button>
              </div>

              {selectedRoadmap ? (
                <div className="kmk-card" style={{ marginBottom: 20 }}>
                  <h3 style={{ margin: 0, fontFamily: "Playfair Display", color: "var(--gold)" }}>
                    Roadmap for: {selectedRoadmap.targetRole}
                  </h3>
                  <p style={{ fontSize: "12px", color: "var(--ink-2)" }}>Timeline: {selectedRoadmap.body.timelineMonths || 6} Months</p>

                  <div className="kmk-section-title"><span className="bar"></span>Weekly Goals</div>
                  <ul style={{ paddingLeft: 18, fontSize: "13px", lineHeight: "1.6" }}>
                    {(selectedRoadmap.body.weeklyGoals || []).map((goal, i) => (
                      <li key={i} style={{ marginBottom: 6 }}>{goal}</li>
                    ))}
                  </ul>

                  <div className="kmk-section-title"><span className="bar"></span>Monthly Milestones</div>
                  <ul style={{ paddingLeft: 18, fontSize: "13px", lineHeight: "1.6" }}>
                    {(selectedRoadmap.body.monthlyGoals || []).map((m, i) => (
                      <li key={i} style={{ marginBottom: 6 }}>Month {m.month}: {m.goal}</li>
                    ))}
                  </ul>

                  <div className="kmk-section-title"><span className="bar"></span>Key Recommendations</div>
                  <div style={{ fontSize: "12.5px" }}>
                    <p><b>Courses:</b> {(selectedRoadmap.body.courses || []).join(", ") || "None"}</p>
                    <p><b>Projects:</b> {(selectedRoadmap.body.projects || []).join(", ") || "None"}</p>
                    <p><b>Certifications:</b> {(selectedRoadmap.body.certifications || []).join(", ") || "None"}</p>
                  </div>
                </div>
              ) : (
                <div className="kmk-empty-note">
                  Enter a target role to build a weekly roadmap matching your skills.
                </div>
              )}

              <div className="kmk-section-title"><span className="bar"></span>Generated Roadmap History</div>
              <div className="kmk-file-list">
                {roadmaps.map((r) => (
                  <div key={r.id} className="kmk-role-row" style={{ cursor: "pointer" }} onClick={() => setSelectedRoadmap(r)}>
                    <div className="kmk-role-name">{r.targetRole}</div>
                    <div style={{ fontSize: "11px", color: "var(--ink-2)" }}>
                      {new Date(r.createdAt).toLocaleDateString()}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* VIEW: PROFILE */}
          {view === "profile" && profile && (
            <div>
              <div className="kmk-profile-head">
                <div className="kmk-avatar">AR</div>
                <div>
                  <div className="kmk-profile-name">{profile.name}</div>
                  <div className="kmk-profile-role">{profile.targetRole || "Aspirant Career Explorer"}</div>
                </div>
              </div>

              <div className="kmk-info-grid">
                <div className="kmk-info-item">
                  <label>Target Role</label>
                  {editingProfile ? (
                    <input type="text" value={profile.targetRole} onChange={(e) => setProfile({ ...profile, targetRole: e.target.value })} />
                  ) : (
                    <div>{profile.targetRole || "Not specified"}</div>
                  )}
                </div>
                <div className="kmk-info-item">
                  <label>Experience Level</label>
                  {editingProfile ? (
                    <input type="text" value={profile.experienceLevel} onChange={(e) => setProfile({ ...profile, experienceLevel: e.target.value })} />
                  ) : (
                    <div>{profile.experienceLevel || "Student / Entry"}</div>
                  )}
                </div>
                <div className="kmk-info-item">
                  <label>Preferred Region</label>
                  {editingProfile ? (
                    <input type="text" value={profile.region} onChange={(e) => setProfile({ ...profile, region: e.target.value })} />
                  ) : (
                    <div>{profile.region || "Not specified"}</div>
                  )}
                </div>
                <div className="kmk-info-item">
                  <label>Expected Salary Band</label>
                  {editingProfile ? (
                    <input type="text" value={profile.expectedSalary} onChange={(e) => setProfile({ ...profile, expectedSalary: e.target.value })} />
                  ) : (
                    <div>{profile.expectedSalary || "Not specified"}</div>
                  )}
                </div>
              </div>

              {editingProfile ? (
                <button className="kmk-auth-submit" style={{ width: "auto", padding: "8px 16px", marginBottom: 20 }} onClick={handleSaveProfile}>
                  Save Profile
                </button>
              ) : (
                <button className="kmk-auth-submit" style={{ width: "auto", padding: "8px 16px", marginBottom: 20, background: "transparent", border: "1px solid var(--line)", color: "var(--teal-bright)" }} onClick={() => setEditingProfile(true)}>
                  Edit Profile
                </button>
              )}

              <div className="kmk-section-title"><span className="bar"></span>Blended Career Objective</div>
              <div className="kmk-card" style={{ fontSize: "13px", lineHeight: "1.6", fontStyle: "italic", marginBottom: 20 }}>
                "{profile.careerObjective || "Upload your resume to generate a custom objective summarizing your professional twin."}"
              </div>

              <div className="kmk-section-title"><span className="bar"></span>Skill Profile Matrix</div>
              <div style={{ marginBottom: 20 }}>
                {profile.skillPercentages && profile.skillPercentages.length > 0 ? (
                  profile.skillPercentages.map((s, i) => (
                    <div key={i} className="kmk-skill-row">
                      <div className="kmk-skill-top"><span>{s.name}</span><span>{s.pct}%</span></div>
                      <div className="kmk-skill-track"><div className="kmk-skill-fill" style={{ width: `${s.pct}%` }} /></div>
                    </div>
                  ))
                ) : (
                  <div className="kmk-empty-note">No skills parsed yet. Upload your resume to inspect your skills profile!</div>
                )}
              </div>

              <div className="kmk-section-title"><span className="bar"></span>AI-Extracted Strengths</div>
              <div className="kmk-suggest-row">
                {(profile.strengths || []).map((str, i) => (
                  <div key={i} className="kmk-suggest" style={{ cursor: "default" }}>{str}</div>
                ))}
              </div>

              <div className="kmk-section-title"><span className="bar"></span>Areas to Improve</div>
              <div className="kmk-suggest-row">
                {(profile.weaknesses || []).map((wk, i) => (
                  <div key={i} className="kmk-suggest" style={{ cursor: "default", color: "#e07b7b", borderColor: "#5a3a3a" }}>{wk}</div>
                ))}
              </div>
            </div>
          )}

          {/* VIEW: ACHIEVEMENTS */}
          {view === "achievements" && (
            <div>
              <div className="kmk-xp-bar-wrap">
                <div className="kmk-xp-top">
                  <span className="lvl">Pipeline Grade</span>
                  <span className="xp">
                    {achievements.filter((a) => a.unlocked).length}/{achievements.length} Unlocked
                  </span>
                </div>
                <div className="kmk-xp-track">
                  <div className="kmk-xp-fill" style={{ width: `${(achievements.filter((a) => a.unlocked).length / (achievements.length || 1)) * 100}%` }} />
                </div>
              </div>

              <div className="kmk-ach-grid">
                {achievements.map((a, i) => (
                  <div key={i} className={`kmk-ach ${a.unlocked ? "" : "locked"}`}>
                    {a.unlocked && <div className="kmk-ach-badge">UNLOCKED</div>}
                    <div className="kmk-ach-icon">{a.icon}</div>
                    <div className="kmk-ach-name">{a.name}</div>
                    <div className="kmk-ach-desc">{a.desc}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* VIEW: DASHBOARD */}
          {view === "dashboard" && (
            <div>
              {loadingDashboard ? (
                <div className="kmk-loading-msg">Refreshing career twin analytics...</div>
              ) : dashboard ? (
                <div>
                  <div className="kmk-grid" style={{ marginBottom: 20 }}>
                    <div className="kmk-card"><h4>Readiness Score</h4><div className="big">{dashboard.careerScore}</div></div>
                    <div className="kmk-card"><h4>Resume Score</h4><div className="big">{dashboard.resumeScore}%</div></div>
                    <div className="kmk-card"><h4>Roadmaps Tracked</h4><div className="big">{dashboard.roadmapProgress}</div></div>
                    <div className="kmk-card"><h4>Achievements Unlocked</h4><div className="big">{dashboard.achievementProgress}</div></div>
                  </div>

                  <div className="kmk-section-title"><span className="bar"></span>Action Feed</div>
                  <div>
                    {dashboard.recentActivity && dashboard.recentActivity.length > 0 ? (
                      dashboard.recentActivity.map((act, i) => (
                        <div key={i} className="kmk-activity-row">
                          <div className="kmk-activity-tag">{act.type}</div>
                          <div className="kmk-activity-text">{act.detail}</div>
                          <div className="kmk-activity-time">{new Date(act.at).toLocaleTimeString()}</div>
                        </div>
                      ))
                    ) : (
                      <div className="kmk-empty-note">No actions logged yet. Upload files or chat to start generating feed!</div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="kmk-error-msg">Failed to fetch dashboard snapshot.</div>
              )}
            </div>
          )}

          {/* VIEW: ML LAB */}
          {view === "ml_lab" && (
            <div className="kmk-ml-container">
              {/* Tabs */}
              <div className="kmk-ml-tabs">
                <button className={`kmk-ml-tab ${mlTab === "dataset" ? "active" : ""}`} onClick={() => setMlTab("dataset")}>1. Kaggle Dataset Explorer</button>
                <button className={`kmk-ml-tab ${mlTab === "classifiers" ? "active" : ""}`} onClick={() => setMlTab("classifiers")}>2. Classifier Arena</button>
                <button className={`kmk-ml-tab ${mlTab === "regression" ? "active" : ""}`} onClick={() => setMlTab("regression")}>3. Salary Regressor Sandbox</button>
                <button className={`kmk-ml-tab ${mlTab === "clustering" ? "active" : ""}`} onClick={() => setMlTab("clustering")}>4. K-Means Skill Clustering</button>
                <button className={`kmk-ml-tab ${mlTab === "theory" ? "active" : ""}`} onClick={() => setMlTab("theory")}>5. ML Theory Guide</button>
              </div>

              {/* TAB: DATASET */}
              {mlTab === "dataset" && (
                <div className="kmk-ml-panel">
                  {loadingDataset ? (
                    <div className="kmk-loading-msg">Reading career_data.csv and aggregating statistics...</div>
                  ) : datasetData ? (
                    <div>
                      <div className="kmk-section-title"><span className="bar"></span>Dataset Information</div>
                      <p style={{ fontSize: "13px" }}>
                        This dataset models professional careers. It contains <b>{datasetData.totalRows}</b> records. Target outputs are <b>Role</b> (for Classification) and <b>Expected_Salary</b> (for Regression).
                      </p>

                      <div className="kmk-section-title"><span className="bar"></span>Numerical Statistics Summary</div>
                      <div className="kmk-ml-table-wrap" style={{ marginBottom: 20 }}>
                        <table className="kmk-ml-table">
                          <thead>
                            <tr>
                              <th>Feature Column</th>
                              <th>Data Type</th>
                              <th>Mean</th>
                              <th>Std Dev</th>
                              <th>Min</th>
                              <th>Max</th>
                              <th>Nulls</th>
                            </tr>
                          </thead>
                          <tbody>
                            {datasetData.summary.map((col, idx) => (
                              <tr key={idx}>
                                <td style={{ fontWeight: 600, color: "var(--teal-bright)" }}>{col.column}</td>
                                <td>{col.type}</td>
                                <td>{col.mean}</td>
                                <td>{col.std}</td>
                                <td>{col.min}</td>
                                <td>{col.max}</td>
                                <td>{col.missing}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      <div className="kmk-section-title"><span className="bar"></span>Sample Records Preview (First 15 Rows)</div>
                      <div className="kmk-ml-table-wrap">
                        <table className="kmk-ml-table">
                          <thead>
                            <tr>
                              {datasetData.columns.map((c, i) => <th key={i}>{c.replace("_", " ")}</th>)}
                            </tr>
                          </thead>
                          <tbody>
                            {datasetData.samples.slice(0, 15).map((row, idx) => (
                              <tr key={idx}>
                                <td>{row.Experience_Years} yrs</td>
                                <td>{row.Python_Score}</td>
                                <td>{row.ML_Score}</td>
                                <td>{row.SQL_Score}</td>
                                <td>{row.WebDev_Score}</td>
                                <td>{row.SystemDesign_Score}</td>
                                <td>{row.Communication_Score}</td>
                                <td>{row.Certifications_Count}</td>
                                <td style={{ color: "var(--gold)", fontWeight: "bold" }}>₹{row.Expected_Salary}L</td>
                                <td style={{ color: "var(--teal-bright)", fontWeight: "bold" }}>{row.Role}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : (
                    <div className="kmk-error-msg">Failed to load dataset records.</div>
                  )}
                </div>
              )}

              {/* TAB: CLASSIFIERS */}
              {mlTab === "classifiers" && (
                <div className="kmk-ml-panel">
                  <div className="kmk-ml-lab-layout">
                    {/* Controls */}
                    <div className="kmk-ml-controls">
                      <h3 style={{ margin: "0 0 10px 0", color: "var(--gold)", fontFamily: "Playfair Display" }}>Model Settings</h3>
                      
                      <div className="kmk-ml-control-group">
                        <label>Select Algorithm</label>
                        <select value={selectedClassifier} onChange={(e) => setSelectedClassifier(e.target.value)}>
                          <option value="random_forest">Random Forest Classifier (Ensemble Bagging)</option>
                          <option value="logistic_regression">Logistic Regression (Linear Classifier)</option>
                          <option value="svm">Support Vector Machine (SVC)</option>
                          <option value="knn">K-Nearest Neighbour (KNN)</option>
                          <option value="decision_tree">Decision Tree Classifier</option>
                          <option value="naive_bayes">Naive Bayes Classifier (GaussianNB)</option>
                          <option value="perceptron">Perceptron Algorithm</option>
                          <option value="bagging">Bagging Classifier (Bootstrap Ensemble)</option>
                          <option value="boosting">Gradient Boosting (Boosting Ensemble)</option>
                        </select>
                      </div>

                      <div className="kmk-ml-control-group">
                        <label>Train-Test Split Ratio: <span>{Math.round((1 - clfSplit)*100)}/{Math.round(clfSplit*100)}</span></label>
                        <input type="range" min="0.1" max="0.4" step="0.05" value={clfSplit} onChange={(e) => setClfSplit(e.target.value)} />
                      </div>

                      <div className="kmk-ml-control-group">
                        <label>Feature Scaling & Normalization</label>
                        <select value={clfScaling} onChange={(e) => setClfScaling(e.target.value)}>
                          <option value="none">None (Raw Scores)</option>
                          <option value="standard">StandardScaler (Mean=0, Var=1)</option>
                          <option value="minmax">MinMaxScaler (Range [0, 1])</option>
                        </select>
                      </div>

                      {/* Hyperparameters based on selected model */}
                      {selectedClassifier === "knn" && (
                        <div className="kmk-ml-control-group">
                          <label>N Neighbors (K): <span>{clfParams.n_neighbors}</span></label>
                          <input type="range" min="1" max="15" step="2" value={clfParams.n_neighbors} onChange={(e) => setClfParams({ ...clfParams, n_neighbors: e.target.value })} />
                        </div>
                      )}

                      {selectedClassifier === "decision_tree" && (
                        <div className="kmk-ml-control-group">
                          <label>Max Depth: <span>{clfParams.max_depth}</span></label>
                          <input type="range" min="2" max="12" step="1" value={clfParams.max_depth} onChange={(e) => setClfParams({ ...clfParams, max_depth: e.target.value })} />
                        </div>
                      )}

                      {selectedClassifier === "random_forest" && (
                        <div className="kmk-ml-control-group">
                          <label>N Estimators (Trees): <span>{clfParams.n_estimators}</span></label>
                          <input type="range" min="10" max="100" step="10" value={clfParams.n_estimators} onChange={(e) => setClfParams({ ...clfParams, n_estimators: e.target.value })} />
                        </div>
                      )}

                      {selectedClassifier === "svm" && (
                        <div className="kmk-ml-control-group">
                          <label>Regularization C: <span>{clfParams.C}</span></label>
                          <input type="range" min="0.1" max="5.0" step="0.5" value={clfParams.C} onChange={(e) => setClfParams({ ...clfParams, C: e.target.value })} />
                        </div>
                      )}

                      <button className="kmk-auth-submit" style={{ marginTop: 10 }} onClick={handleTrainClassifier} disabled={trainingClassifier}>
                        {trainingClassifier ? "Running gradient optimizations..." : "Train Classifier Model"}
                      </button>
                    </div>

                    {/* Output */}
                    <div className="kmk-ml-metrics">
                      <h3 style={{ margin: 0, color: "var(--gold)", fontFamily: "Playfair Display" }}>Training Outcomes</h3>
                      
                      {clfMetrics ? (
                        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                          <h4 style={{ margin: 0, color: "var(--teal-bright)" }}>{clfMetrics.modelName}</h4>
                          <div className="kmk-ml-metric-grid">
                            <div className="kmk-ml-metric-card">
                              <label>Train Accuracy</label>
                              <div className="val">{clfMetrics.trainAccuracy}%</div>
                            </div>
                            <div className="kmk-ml-metric-card">
                              <label>Test Accuracy</label>
                              <div className="val">{clfMetrics.testAccuracy}%</div>
                            </div>
                            <div className="kmk-ml-metric-card">
                              <label>F1-Score (Weighted)</label>
                              <div className="val">{clfMetrics.f1Score}%</div>
                            </div>
                            <div className="kmk-ml-metric-card">
                              <label>5-Fold Cross Val</label>
                              <div className="val">{clfMetrics.crossValScore}%</div>
                            </div>
                          </div>
                          
                          <div style={{ fontSize: "12px", background: "var(--navy-900)", padding: 10, borderRadius: 8 }}>
                            <p style={{ margin: "0 0 6px 0" }}><b>Model Status:</b> <span style={{ color: clfMetrics.status.includes("Optimal") ? "var(--teal-bright)" : "#e07b7b" }}>{clfMetrics.status}</span></p>
                            <p style={{ margin: "0 0 6px 0" }}><b>Training Duration:</b> {clfMetrics.fitTime} seconds</p>
                            <p style={{ margin: 0 }}><b>Inductive Bias:</b> {clfMetrics.inductiveBias}</p>
                          </div>
                        </div>
                      ) : (
                        <div className="kmk-empty-note">Configure options and click train to execute.</div>
                      )}
                    </div>
                  </div>

                  {/* Comparative Table */}
                  <div className="kmk-section-title"><span className="bar"></span>Classifier Comparison Arena (Default Pre-Trained Stats)</div>
                  {loadingComparisons ? (
                    <div className="kmk-loading-msg">Fitting all classifiers iteratively to construct comparison matrix...</div>
                  ) : modelComparisons.length > 0 ? (
                    <div className="kmk-ml-table-wrap">
                      <table className="kmk-ml-table">
                        <thead>
                          <tr>
                            <th>Model</th>
                            <th>Train Accuracy</th>
                            <th>Test Accuracy</th>
                            <th>Precision</th>
                            <th>Recall</th>
                            <th>F1-Score</th>
                            <th>5-Fold CV</th>
                            <th>Fit Time</th>
                          </tr>
                        </thead>
                        <tbody>
                          {modelComparisons.map((c, idx) => (
                            <tr key={idx}>
                              <td style={{ fontWeight: 600, color: "var(--gold)" }}>{c.modelName}</td>
                              <td>{c.trainAccuracy}%</td>
                              <td style={{ fontWeight: "bold", color: "var(--teal-bright)" }}>{c.testAccuracy}%</td>
                              <td>{c.precision}%</td>
                              <td>{c.recall}%</td>
                              <td style={{ fontWeight: "bold" }}>{c.f1Score}%</td>
                              <td>{c.crossValScore}%</td>
                              <td>{c.fitTime}s</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="kmk-error-msg">Failed to load classifier comparative metrics.</div>
                  )}
                </div>
              )}

              {/* TAB: REGRESSION */}
              {mlTab === "regression" && (
                <div className="kmk-ml-panel">
                  <div className="kmk-ml-lab-layout">
                    {/* Controls */}
                    <div className="kmk-ml-controls">
                      <h3 style={{ margin: "0 0 10px 0", color: "var(--gold)", fontFamily: "Playfair Display" }}>Salary Regressor Settings</h3>
                      
                      <div className="kmk-ml-control-group">
                        <label>Algorithm Selection</label>
                        <select value={selectedRegressor} onChange={(e) => setSelectedRegressor(e.target.value)}>
                          <option value="multiple_linear">Multiple Linear Regression (All Features to Salary)</option>
                          <option value="simple_linear">Simple Linear Regression (Experience to Salary)</option>
                          <option value="polynomial">Polynomial Regression (Exp & ML Degree 2 to Salary)</option>
                          <option value="bayesian_linear">Bayesian Ridge Regression (Regularized to Salary)</option>
                        </select>
                      </div>

                      <div className="kmk-ml-control-group">
                        <label>Train-Test Split Ratio: <span>{Math.round((1 - regSplit)*100)}/{Math.round(regSplit*100)}</span></label>
                        <input type="range" min="0.1" max="0.4" step="0.05" value={regSplit} onChange={(e) => setRegSplit(e.target.value)} />
                      </div>

                      <div className="kmk-ml-control-group">
                        <label>Feature Scaling</label>
                        <select value={regScaling} onChange={(e) => setRegScaling(e.target.value)}>
                          <option value="none">None (Raw Inputs)</option>
                          <option value="standard">StandardScaler</option>
                          <option value="minmax">MinMaxScaler</option>
                        </select>
                      </div>

                      {selectedRegressor === "polynomial" && (
                        <div className="kmk-ml-control-group">
                          <label>Polynomial Degree: <span>{regParams.degree}</span></label>
                          <input type="range" min="2" max="4" step="1" value={regParams.degree} onChange={(e) => setRegParams({ ...regParams, degree: e.target.value })} />
                        </div>
                      )}

                      <button className="kmk-auth-submit" style={{ marginTop: 10 }} onClick={handleTrainRegressor} disabled={trainingRegressor}>
                        {trainingRegressor ? "Computing least-squares residuals..." : "Train Regressor Model"}
                      </button>
                    </div>

                    {/* Output */}
                    <div className="kmk-ml-metrics">
                      <h3 style={{ margin: 0, color: "var(--gold)", fontFamily: "Playfair Display" }}>Regression Outcomes</h3>
                      
                      {regMetrics ? (
                        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                          <h4 style={{ margin: 0, color: "var(--teal-bright)" }}>{regMetrics.modelName}</h4>
                          <div className="kmk-ml-metric-grid">
                            <div className="kmk-ml-metric-card">
                              <label>Test MSE (Error)</label>
                              <div className="val" style={{ color: "#e07b7b" }}>{regMetrics.testMSE}</div>
                            </div>
                            <div className="kmk-ml-metric-card">
                              <label>Test RMSE (Std Error)</label>
                              <div className="val" style={{ color: "#e07b7b" }}>{regMetrics.testRMSE}</div>
                            </div>
                            <div className="kmk-ml-metric-card">
                              <label>Train R² Score</label>
                              <div className="val">{regMetrics.trainR2}%</div>
                            </div>
                            <div className="kmk-ml-metric-card">
                              <label>Test R² Score</label>
                              <div className="val">{regMetrics.testR2}%</div>
                            </div>
                          </div>
                          
                          <div style={{ fontSize: "12px", background: "var(--navy-900)", padding: 10, borderRadius: 8 }}>
                            <p style={{ margin: "0 0 6px 0" }}><b>Training MSE:</b> {regMetrics.trainMSE} (LPA squared)</p>
                            <p style={{ margin: "0 0 6px 0" }}><b>R² Interpretation:</b> Explains {regMetrics.testR2}% of salary variance on testing split.</p>
                            <p style={{ margin: 0 }}><b>Inductive Bias:</b> {regMetrics.inductiveBias}</p>
                          </div>
                        </div>
                      ) : (
                        <div className="kmk-empty-note">Configure options and click train to compute regression errors.</div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* TAB: CLUSTERING */}
              {mlTab === "clustering" && (
                <div className="kmk-ml-panel">
                  <div className="kmk-ml-lab-layout">
                    {/* Controls */}
                    <div className="kmk-ml-controls">
                      <h3 style={{ margin: "0 0 10px 0", color: "var(--gold)", fontFamily: "Playfair Display" }}>K-Means Clustering Setup</h3>
                      
                      <div className="kmk-ml-control-group">
                        <label>Number of Clusters (K): <span>{clusterK}</span></label>
                        <input type="range" min="2" max="6" step="1" value={clusterK} onChange={(e) => setClusterK(e.target.value)} />
                      </div>
                      
                      <p style={{ fontSize: "12px", color: "var(--ink-2)" }}>
                        Unsupervised learning clusters candidates based solely on their 6 skill dimensions (Python, ML, SQL, WebDev, SystemDesign, Communication).
                      </p>

                      <button className="kmk-auth-submit" style={{ marginTop: 10 }} onClick={handleRunClustering} disabled={runningClustering}>
                        {runningClustering ? "Running expectation maximization..." : "Run K-Means Clustering"}
                      </button>
                    </div>

                    {/* Output */}
                    <div className="kmk-ml-metrics">
                      <h3 style={{ margin: 0, color: "var(--gold)", fontFamily: "Playfair Display" }}>Cluster Center Centroids</h3>
                      
                      {clusterResults.length > 0 ? (
                        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                          {clusterResults.map((c, i) => (
                            <div key={i} style={{ background: "var(--navy-900)", padding: 12, borderRadius: 8, border: "1px solid var(--line)" }}>
                              <h4 style={{ margin: "0 0 6px 0", color: "var(--teal-bright)" }}>
                                Cluster #{c.clusterId + 1}: {c.label} ({c.size} profiles)
                              </h4>
                              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "6px", fontSize: "11px", fontFamily: "JetBrains Mono" }}>
                                {Object.entries(c.centerAverages).map(([skill, val]) => (
                                  <div key={skill}>{skill}: <b>{val}%</b></div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="kmk-empty-note">Run K-Means to identify clusters.</div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* TAB: THEORY */}
              {mlTab === "theory" && (
                <div className="kmk-theory-grid">
                  <div className="kmk-theory-card">
                    <h3>Types of Learning</h3>
                    <p><b>Supervised Learning:</b> Models learn mapping from inputs to labeled targets. Classifier outputs <i>Role</i>; Regressor outputs <i>Salary</i>.</p>
                    <p><b>Unsupervised Learning:</b> Algorithm groups data without any explicit labels. K-Means clusters users into profiles based on skill sets.</p>
                    <p><b>Semi-Supervised:</b> Mix of labeled and unlabeled data to improve accuracy when labeling costs are high.</p>
                  </div>
                  
                  <div className="kmk-theory-card">
                    <h3>Hypothesis Space & Bias</h3>
                    <p><b>Hypothesis Space (H):</b> The set of all possible mapping functions a model can choose from.</p>
                    <p><b>Inductive Bias:</b> The assumptions a model makes to generalise beyond training data (e.g. SVM prefers wide margins; KNN assumes similar proximity; Naive Bayes assumes independent parameters).</p>
                  </div>

                  <div className="kmk-theory-card">
                    <h3>Bias vs. Variance Trade-off</h3>
                    <p><b>Bias Error:</b> Underfitting. Assumptions are too simple (low train & test scores). Simple linear models exhibit high bias.</p>
                    <p><b>Variance Error:</b> Overfitting. Model memorizes noise (high train score, low test score). High tree count or deep Decision Trees exhibit high variance.</p>
                  </div>

                  <div className="kmk-theory-card">
                    <h3>Optimization: Gradient Descent</h3>
                    <p><b>Gradient Descent:</b> Iterative optimization algorithm used to minimize cost/loss functions by updating weights proportional to negative gradients.</p>
                    <p>Features are scaled (StandardScaler/MinMax) so that the loss function contours are circular, allowing Gradient Descent to converge to the global minimum faster.</p>
                  </div>

                  <div className="kmk-theory-card">
                    <h3>Evaluation Metrics Reference</h3>
                    <p><b>Classification:</b> Accuracy (fraction of correct guesses), Precision (true positives / predicted positives), Recall (true positives / actual positives), F1-Score (harmonic mean of Precision & Recall).</p>
                    <p><b>Regression:</b> Mean Squared Error (MSE) penalizes large outliers. Root Mean Squared Error (RMSE) returns values in original target units (Lakhs INR).</p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* SETTINGS MODAL */}
      {settingsModalOpen && (
        <div className="kmk-modal-backdrop">
          <div className="kmk-modal">
            <h3>Settings</h3>
            <div className="kmk-modal-row">
              <span>AI Engine</span>
              <span>{settings.preferredAIModel.toUpperCase()}</span>
            </div>
            <div className="kmk-modal-row">
              <span>Enable In-App Notifications</span>
              <input
                type="checkbox"
                checked={settings.notificationsEnabled}
                onChange={(e) => handleSaveSettings(e.target.checked)}
              />
            </div>
            <button className="kmk-modal-close" onClick={() => setSettingsModalOpen(false)}>Close Settings</button>
          </div>
        </div>
      )}
    </div>
  );
}
