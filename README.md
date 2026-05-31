# 🧭 CodeAtlas AI

Understand any GitHub repository in minutes, not days.

## 🎯 Impact

**Input:** GitHub repository URL  
**Output:** Tech stack + AI summary + Architecture diagram + Engineering recommendations  
**Time to Insight:** Under 60 seconds


---

## 🏆 Microsoft Build AI Hackathon 2026

**Team Name:** CodeAtlas

---

## 🔗 Live Demo & Resources

| Resource | Link |
|----------|------|
| 🚀 Live Frontend | https://codeatlas-frontend-khaki.vercel.app/ |
| ⚙️ Backend API | https://codeatlas-backend-5hnr.onrender.com/docs |
| 💻 Frontend Repository | https://github.com/sejalsksagar/codeatlas-frontend/ |
| 🛠️ Backend Repository | https://github.com/sejalsksagar/codeatlas-backend/ |

## 🎬 Theme

AI at Work: Productivity & Teamwork Reimagined

## 🔍 Problem Statement

Developers spend significant time understanding unfamiliar codebases.

### ⚡ Common challenges:
- 📚 Missing or outdated documentation
- 🖼️ No architecture diagrams
- 👨‍💼 Knowledge concentrated with senior engineers
- 🎓 Slow onboarding for new contributors
- 📦 Difficulty evaluating open-source projects

These challenges reduce developer productivity and make collaboration harder across teams.

## 💡 Solution

CodeAtlas AI transforms any public GitHub repository into understandable engineering knowledge.

Paste a GitHub repository URL and receive:

- 🔧 Technology stack detection
- 📝 Project summary in plain English
- 📦 Module-level explanations
- 🏗️ Architecture diagram visualization
- 🔒 Security recommendations
- ⚡ Performance recommendations
- 📈 Scalability recommendations

Our goal is to reduce repository onboarding from days to minutes.

## 🏗️ Architecture Overview

```text
👤 User
  ↓
🎨 Next.js Frontend (Vercel)
  ↓
⚙️ FastAPI Backend (Render)
  ↓
🐙 GitHub API
  ↓
📦 Repository Structure Analysis
  ↓
🧠 GitHub Models (GPT-5)
  ↓
📝 Mermaid Architecture Generation
  ↓
🎭 React Flow Visualization
  ↓
📊 Summary + Diagram + Suggestions
```

## 🛠️ Technology Stack

### 🔧 Backend
- FastAPI
- Pydantic
- Python

### 🎨 Frontend
- Next.js 14
- React
- TypeScript
- Tailwind CSS
- React Flow

### 🤖 AI Layer
- GitHub Models (GPT-5)
- GitHub REST API

### ☁️ Infrastructure
- Render
- Vercel
- GitHub Actions

---

## 📸 Screenshots

### 1. Landing Page

Repository URL input screen where users can submit any public GitHub repository for analysis.

**Highlights:**

* Clean onboarding experience
* Repository URL validation
* Single-click analysis workflow

<img width="1884" height="886" alt="CodeAtlas_Landing_Page" src="https://github.com/user-attachments/assets/c4011a34-1d39-4e05-ad36-77e3b489f1d7" />


---

### 2. Repository Analysis Dashboard

Generated repository overview showing detected technology stack, AI-generated project summary, module explanations, and request flow.

**Highlights:**

* Automatic tech stack detection
* Plain-English repository understanding
* Module-level insights
* AI-powered analysis using GitHub Models GPT-5

<img width="1782" height="899" alt="image" src="https://github.com/user-attachments/assets/614351e8-a1e2-4f20-9bc7-f8c44260e4ab" />


---

### 3. Architecture Diagram Visualization

GPT-5 generated architecture diagram rendered using React Flow.

**Highlights:**

* Automatic architecture generation
* Interactive visualization
* Drag-and-reposition nodes
* Clear system understanding at a glance

*Screenshot:* `screenshots/architecture-diagram.png`

---

### 4. Engineering Recommendations

AI-generated recommendations categorized by security, performance, scalability, and engineering quality.

**Highlights:**

* Actionable repository insights
* Security recommendations
* Performance improvement opportunities
* Scalability suggestions

*Screenshot:* `screenshots/recommendations.png`


## 🧩 Microsoft AI Stack Usage

This project leverages the Microsoft ecosystem through:

- 🧠 GitHub Models (GPT-5)
- 🐙 GitHub REST API
- ⚙️ GitHub Actions
- 🤖 GitHub Copilot

GitHub Models GPT-5 powers repository understanding, architecture generation, and engineering recommendations.

## 🤖 AI Tools Disclosure

The following AI tools were used during development:

- 💬 ChatGPT – architecture discussions and implementation guidance
- 🧠 Claude – planning and code review assistance
- ✨ Gemini – alternative solution exploration
- 🤖 GitHub Copilot – README generation, documentation assistance, and developer productivity support
- 🧠 GitHub Models GPT-5 – runtime AI inference inside the application

All generated code and outputs were reviewed, tested, and validated by the team.

## 🚀 Setup Instructions

### Backend

```bash
git clone https://github.com/sejalsksagar/codeatlas-backend.git
cd codeatlas-backend
python -m venv venv
pip install -r requirements.txt
uvicorn main:app --reload
```

Environment Variables:

```env
GITHUB_TOKEN=
GITHUB_MODELS_TOKEN=
ALLOWED_ORIGINS=
```

### Frontend

For frontend setup, refer to:

https://github.com/sejalsksagar/codeatlas-frontend

## 🔄 CI/CD

GitHub Actions automatically executes backend tests on every push.

## 🚀 Future Improvements

- ✏️ Fully editable React Flow diagrams
- 📥 Diagram export functionality
- 💬 Repository chat assistant
- 📊 UML diagram generation
- 🗄️ Database schema visualization
- 🔒 Private repository support
- 🔀 Multi-repository analysis
- 📈 API usage analytics
- 🚀 Automated deployment workflows

## 👥 Team CodeAtlas

### Sejal Kshirsagar
- Role: Backend Engineering & AI Integration
- LinkedIn: https://www.linkedin.com/in/sejalsksagar/

### Priya Sharma
- Role: Frontend Engineering & UI/UX
- LinkedIn: https://www.linkedin.com/in/priya-sharma-mitwpu/

### Soumyashri Singha
- Role: Architecture, Integration & Product Presentation
- LinkedIn: https://www.linkedin.com/in/soumyashri-singha-6850a2210/

## 🔗 Project Links

- 🚀 Frontend: https://codeatlas-frontend-khaki.vercel.app/
- ⚙️ Backend API: https://codeatlas-backend-5hnr.onrender.com/docs
- 💻 Frontend Repository: https://github.com/sejalsksagar/codeatlas-frontend/
- 🛠️ Backend Repository: https://github.com/sejalsksagar/codeatlas-backend/

---

Made with ❤️ by Team CodeAtlas for Microsoft Build AI Hackathon 2026
