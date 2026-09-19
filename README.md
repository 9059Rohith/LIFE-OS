<div align="center">
  
# 🌌 LIFE-OS

**The ultimate intelligence engine for your digital life.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![React Version](https://img.shields.io/badge/React-18.2.0-61dafb.svg)](https://reactjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.95+-009688.svg)](https://fastapi.tiangolo.com)
[![Render Deployment](https://img.shields.io/badge/Deployed_on-Render-46E3B7?style=flat&logo=render&logoColor=white)](https://render.com)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#contributing)

*LIFE-OS is a hyper-connected, distributed event-based system that unifies your workflows, communication, and knowledge into a single, intelligent interface.*

**Track fit:** Next-Gen Productivity & Automation. LIFEOS demonstrates AI-assisted workflow orchestration, approval-bound execution and verifiable automation for repetitive consequence-management work.

**Reviewer links:** [Architecture](ARCHITECTURE.md) | [AI usage](AI_USAGE.md) | [Security](SECURITY.md) | [Hackathon alignment](docs/HACKATHON_ALIGNMENT.md) | [Demo script](docs/demo-script.md) | [Final release report](docs/FINAL_RELEASE_REPORT.md) | [Poster](docs/poster/lifeos-poster.svg) | [ScreenOps benchmark review](docs/SCREENOPS_COMPARISON.md)

This repository includes a React command center, a FastAPI service, durable application state, a Windows shell for the actual Discord and WhatsApp websites, provider adapters and deployment configuration. The default configuration is live mode with an empty workspace. A separate live Railway service is deployed, while the existing public demo retains labeled local records. **The live product is not yet fully accepted**; see [current release status](docs/RELEASE_STATUS.md). Account registration and isolated work records are available behind an off-by-default setting; connected provider actions remain restricted to the primary owner.

---
</div>

## 📖 Table of Contents

- [Vision & Philosophy](#-vision--philosophy)
- [Core Features](#-core-features)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [Getting Started (Local Development)](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Environment Configuration](#-environment-configuration)
- [Integrations (The Ripple Engine)](#-integrations)
- [Quality Assurance & Testing](#-quality-assurance)
- [Deployment](#-deployment)
- [Contributing](#-contributing)
- [License](#-license)
- [Acknowledgments](#-acknowledgments)

---

## 🔮 Vision & Philosophy

Modern digital life is fragmented across dozens of apps, platforms, and devices. **LIFE-OS** is designed to be the central nervous system of your digital existence. By ingesting events from diverse platforms (Discord, WhatsApp, Google services) and processing them through the centralized **Ripple Intelligence Engine**, LIFE-OS contextualizes, organizes, and automates your daily digital interactions.

It is more than a dashboard; it is a contextual memory and command center for your life.

## Demo assets

The repository includes a public GitHub demo video artifact at [`docs/demo/lifeos-demo-final.webm`](docs/demo/lifeos-demo-final.webm), the recording script at [`docs/demo-script.md`](docs/demo-script.md), timed subtitles at [`docs/demo/lifeos-demo.srt`](docs/demo/lifeos-demo.srt), generated screenshots in [`docs/screenshots/`](docs/screenshots/) and a poster at [`docs/poster/lifeos-poster.svg`](docs/poster/lifeos-poster.svg). The video was generated from the local LIFEOS demo app; upload it to a streaming host only if the hackathon form rejects a GitHub-hosted video artifact.

## Verification

See [Final release report](docs/FINAL_RELEASE_REPORT.md) for the exact local commands, test results, dependency audits, demo artifact duration and remaining external acceptance gates.

## ✨ Core Features

*   **🌊 Ripple Intelligence Engine:** A centralized event bus that processes inbound information from various provider panels and creates ripple effects across your digital ecosystem.
*   **🔌 Plug-and-Play Integrations:** Seamlessly ingest data from Google, Discord, and WhatsApp.
*   **🧠 Contextual Memory:** Utilizing LLM-powered categorization (via OpenAI/Custom Models) to make sense of your data streams.
*   **💻 Cross-Platform Mastery:** Designed to run via the web, or as an Electron-bridged desktop application.
*   **🔒 Secure by Design:** Token encryption, strict CORS policies, and secure origin validation for live authentication.
*   **⚡ Real-time Feedback:** Beautiful, responsive UI built with modern React, Vite, and carefully crafted micro-interactions.

---

## 🏗 System Architecture

LIFE-OS utilizes a decoupled, event-driven architecture to ensure scalability and reliability:

1.  **Frontend (Client):** A React SPA communicating with the backend via RESTful APIs.
2.  **Backend (API & Logic):** FastAPI handling high-throughput asynchronous requests, background tasks, and AI orchestration.
3.  **Database Layer:** SQLite (for local/embedded deployments) abstracted via ORM for easy migration to PostgreSQL for scale.
4.  **Provider Panels:** Modular ingestion services for 3rd party APIs (Discord bots, WhatsApp webhooks, Google OAuth).

---

## 🛠 Tech Stack

| Domain | Technologies |
| :--- | :--- |
| **Backend** | Python 3.10+, FastAPI, Pydantic, SQLAlchemy, Uvicorn |
| **Frontend** | React 18, Vite, TypeScript, TailwindCSS (Utility logic) |
| **Database** | SQLite (Production-ready local file storage via `data/lifeos.db`) |
| **AI / ML** | OpenAI GPT-4 API (configurable) |
| **Deployment** | Docker, Render/Railway configuration |

---

## 🚀 Getting Started

Follow these instructions to set up a local development environment.

### Prerequisites
*   Node.js (v18+)
*   Python (3.10+)
*   Git

### 1. Backend Setup

```bash
# Clone the repository
git clone https://github.com/9059Rohith/LIFE-OS.git
cd LIFE-OS

# Navigate to backend and create a virtual environment
cd backend
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI server (Port 8010)
python -m uvicorn lifeos.main:app --host 127.0.0.1 --port 8010 --reload
```

### 2. Frontend Setup

```bash
# Open a new terminal and navigate to the frontend directory
cd LIFE-OS/frontend

# Install dependencies
npm install

# Start the Vite development server (Port 5173)
npm run dev
```

---

## ⚙️ Environment Configuration

LIFE-OS requires a `.env` file at the root of the project. **Never commit this file to version control.**

Copy the provided `.env.example` to `.env` and configure your secrets:

```env
# Core Configuration
LIFEOS_MODE=development
LIFEOS_ENVIRONMENT=development
LIFEOS_DATABASE_URL=sqlite:///./data/lifeos.db
LIFEOS_ALLOWED_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]

# Security & Encryption
LIFEOS_AUTH_PASSWORD=your_secure_minimum_16_char_password
LIFEOS_ENCRYPTION_KEY=your_base64_encryption_key

# AI Integration
LIFEOS_OPENAI_API_KEY=your_openai_api_key
LIFEOS_OPENAI_MODEL=gpt-4o-mini

# Provider: Google
LIFEOS_GOOGLE_CLIENT_ID=your_google_client_id
LIFEOS_GOOGLE_CLIENT_SECRET=your_google_client_secret
LIFEOS_GOOGLE_REDIRECT_URI=http://localhost:8010/api/integrations/google/callback

# Provider: Discord
LIFEOS_DISCORD_BOT_TOKEN=your_discord_bot_token
LIFEOS_DISCORD_CHANNEL_ID=your_channel_id

# Provider: WhatsApp
LIFEOS_WHATSAPP_ENABLED=true
```

> **Security Warning:** Ensure your `LIFEOS_ENCRYPTION_KEY` is a valid 32-byte base64 encoded URL-safe string. Keep your API keys and tokens strictly confidential.

---

## 🔗 Integrations

*   **Google:** Enables OAuth2 login and calendar/email event syncing. Set up credentials in the [Google Cloud Console](https://console.cloud.google.com/).
*   **Discord:** Utilize the built-in bot logic to ingest server events directly into your Ripple Engine. Requires a bot token with proper gateway intents.
*   **WhatsApp:** Webhook integration for real-time messaging parsing.

---

## 🧪 Quality Assurance

We maintain a rigorous standard of code quality. LIFE-OS has local verification evidence for backend, frontend, desktop, dependency and secret-scan checks:
- **Backend APIs:** 139 tests passed locally.
- **Frontend & Desktop:** frontend build/lint passed locally; desktop tests passed 7/7.

*To run tests locally, refer to the `tests/` directory and use `pytest` for the backend.*

---

## 🌍 Deployment

LIFE-OS is containerized and ready for cloud deployment. The recommended provider is **Render**.

1.  Connect your GitHub repository to Render.
2.  Create a **Web Service** utilizing the `Dockerfile` present in the repository root.
3.  Add your production environment variables (from your `.env` file) into the Render dashboard.
4.  Render will automatically build and deploy the Docker container exposing the API and serving the built frontend assets.

---

## 🤝 Contributing

We welcome contributions from the community to help make LIFE-OS the ultimate productivity engine!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

## 🙏 Acknowledgments

*   Developed with ❤️ by [9059Rohith](https://github.com/9059Rohith).
*   Built for pushing the boundaries of what a personal operating system can be.
