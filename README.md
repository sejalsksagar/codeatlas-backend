# 🧭 CodeAtlas AI 

Understand any GitHub repository in minutes, not days.

## 🎯 Impact

**Input:** GitHub repository URL  
**Output:** Tech stack + AI summary + Architecture diagram + Engineering recommendations  
**Time to Insight:** Under 60 seconds

---

## 🔗 Live Demo & Resources

- **🚀 Live Frontend:** [https://codeatlas-frontend-khaki.vercel.app/]
- **⚙️ Backend API:** [Render URL](https://codeatlas-backend-5hnr.onrender.com/)
- **💻 Frontend Repository:** [https://github.com/sejalsksagar/codeatlas-frontend/]
- **🛠️ Backend Repository:** [https://github.com/sejalsksagar/codeatlas-backend/]

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

## ✨ Key Features

### 1. 📊 Repository Analysis
- Public GitHub repository ingestion
- Automatic branch detection
- Repository structure understanding

### 2. 🛠️ Technology Detection
- Languages
- Frameworks
- Databases
- Infrastructure tools
- Testing frameworks

### 3. 🤖 AI-Powered Understanding
- Project summaries
- Module explanations
- Architecture generation
- Engineering recommendations

### 4. 🎨 Architecture Visualization
- GPT-5 generated Mermaid architecture
- Rendered using React Flow
- Interactive visualization

### 5. 💎 Improvement Suggestions
- Security insights
- Performance opportunities
- Scalability recommendations
- Engineering quality suggestions

## 🏗️ Architecture Overview

```
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
📊 Summary + Diagram + Suggestions
  ↓
🎭 React Flow Visualization
```

## 🛠️ Technology Stack

### 🔧 Backend
- **FastAPI** - High-performance web framework
- **Pydantic** - Data validation using Python type annotations
- **Python** - Core language

### 🤖 AI Layer
- **GitHub Models** - GPT-5 for AI inference
- **GitHub REST API** - Repository data access

### ☁️ Infrastructure
- **Render** - Backend hosting
- **GitHub Actions** - CI/CD automation

## 🧩 Microsoft AI Stack Usage

This project leverages the Microsoft ecosystem through:

- **🧠 GitHub Models (GPT-5)** - AI inference for repository understanding
- **🐙 GitHub REST API** - Repository data and metadata access
- **⚙️ GitHub Actions** - Automated testing and deployment
- **🤖 GitHub Copilot** - Development assistance

GitHub Models powers the AI capabilities used for repository understanding, architecture generation, and recommendation generation.

## 🤖 AI Tools Disclosure

The following AI tools were used during development:

- **💬 ChatGPT** – Architecture discussions and implementation guidance
- **🧠 Claude** – Planning and code review assistance
- **✨ Gemini** – Alternative solution exploration
- **🤖 GitHub Copilot** – Documentation and implementation assistance
- **🧠 GitHub Models GPT-5** – Runtime AI inference inside the application

All generated code and outputs were reviewed, tested, and validated by the team.

## 📁 Project Structure

### 🔧 Backend Components
- **📊 Repository Analysis APIs** - Endpoints for repository ingestion and processing
- **🐙 GitHub Integration** - Seamless GitHub API integration
- **🤖 AI Integration** - GitHub Models integration for intelligent analysis
- **💡 Recommendation Engine** - Generation of security, performance, and scalability recommendations

### 🎨 Frontend Components (Separate Repository)
- **👨‍💻 User Interface** - Interactive repository analysis interface
- **🎭 Visualization Layer** - Diagram and results rendering
- **🖼️ Diagram Rendering** - React Flow-based architecture visualization
- **📊 Results Presentation** - User-friendly insights display

## 🚀 Setup Instructions

### 🔧 Backend

1. **📥 Clone the repository**
    ```bash
    git clone https://github.com/sejalsksagar/codeatlas-backend.git
    cd codeatlas-backend
    ```

2. **🐍 Create Python virtual environment**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3. **📦 Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4. **⚙️ Configure environment variables**
    Create a `.env` file in the root directory:
    ```
    GITHUB_TOKEN=your_github_token
    GITHUB_MODELS_TOKEN=your_github_models_token
    ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
    ```

5. **▶️ Start FastAPI server**
    ```bash
    uvicorn main:app --reload
    ```

    The API will be available at `http://localhost:8000`

### 🔐 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GITHUB_TOKEN` | GitHub personal access token for API access | Yes |
| `GITHUB_MODELS_TOKEN` | Token for GitHub Models API access | Yes |
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) | Yes |

### 📚 Dependencies

#### 🔧 Backend
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `pydantic` - Data validation
- `pydantic-settings` - Environment configuration
- `tenacity` - Retry logic for API calls

## 🔄 CI/CD

GitHub Actions automatically executes backend tests on every push to ensure code quality and reliability.

## 🎨 Frontend Setup

For frontend installation and setup, refer to the Readme File of [Frontend Repository](https://github.com/sejalsksagar/codeatlas-frontend).

### 🎭 Frontend Stack
- **Next.js 14** - React framework
- **React** - UI library
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Utility-first CSS framework
- **React Flow** - Interactive diagram rendering

## 🚀 Future Improvements

- ✏️ Fully editable React Flow diagrams
- 📥 Diagram export functionality (PNG, SVG, PDF)
- 💬 Repository chat assistant for follow-up questions
- 📊 UML diagram generation
- 🗄️ Database schema visualization
- 🔒 Private repository support with authentication
- 🔀 Multi-repository analysis and comparison
- 🎯 Custom analysis templates
- 📈 API rate limiting and usage analytics
- 🚀 Auto-deploy on render on every commit

## 👥 Team

### 👨‍💻 Member 1
**Role:** Backend Engineering & AI Integration  
**LinkedIn:** [https://www.linkedin.com/in/sejalsksagar/]

### 👩‍💻 Member 2
**Role:** Frontend Engineering & UI/UX  
**LinkedIn:** [https://www.linkedin.com/in/priya-sharma-mitwpu/]

### 👩‍💻 Member 3
**Role:** Architecture, Integration & Product Presentation  
**LinkedIn:** [https://www.linkedin.com/in/soumyashri-singha-6850a2210/]

## 🔗 Project Links

- **🚀 Live Frontend:** [https://codeatlas-frontend-khaki.vercel.app/]
- **⚙️ Backend API:** [https://codeatlas-backend-5hnr.onrender.com/]
- **💻 Frontend Repository:** [https://github.com/sejalsksagar/codeatlas-frontend/]
- **🛠️ Backend Repository:** [https://github.com/sejalsksagar/codeatlas-backend/]

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Made with ❤️ for developers, by developers**
