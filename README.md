<div align="center">

# 🧳 TRIPZ·AI

**Multi-Agent AI Travel Operating System**  
Powered by LangGraph · FastAPI · Next.js

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=flat-square&logo=python&logoColor=white)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?style=flat-square&logo=fastapi&logoColor=white)]()
[![Next.js](https://img.shields.io/badge/Next.js-16.2.6-000000?style=flat-square&logo=next.js&logoColor=white)]()
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-1C3C3C?style=flat-square&logo=langchain&logoColor=white)]()
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)]()
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript&logoColor=white)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)]()

> "Your personal AI travel agent — just describe your dream trip, and let the agents handle the rest."

[✨ Features](#-features) •
[🏗️ Architecture](#️-architecture) •
[⚡ Quick Start](#-quick-start) •
[🧠 How It Works](#-how-it-works) •
[🔧 Configuration](#-configuration)

<br />

<img src="https://raw.githubusercontent.com/hameed-afsar-km/TRIPZ-AI/master/frontend/public/vercel.svg" alt="TRIPZ-AI Banner" width="120" style="border-radius: 16px;" />

<br />

</div>

---

## ✨ Features

| Capability | Description |
|---|---|
| **🌍 Natural Language Input** | Describe your trip in plain English — *"I want to go to Riyadh for 10 days from India"* |
| **🤖 5 Specialized AI Agents** | Supervisor, Router, Curator, Itinerary Builder, and Critic agents collaborate in a LangGraph pipeline |
| **⚡ Real-time Streaming** | Watch each agent work via Server-Sent Events (SSE) — live token streaming |
| **💰 Smart Budgeting** | Automatic budget allocation across transport, hotels, activities, food, and buffer |
| **🌦️ Weather-Aware Planning** | Fetches live 7-day forecasts via Open-Meteo (no API key needed) |
| **🏨 Mock Data Integration** | Hotels, transport, and activities pre-loaded — swap with real APIs in production |
| **🔄 Self-Correcting Pipeline** | Critic agent validates output + optional replanning loop (up to 2 iterations) |
| **🎨 Modern UI** | Next.js 16 + Tailwind CSS v4 + Framer Motion + animated shooting stars |
| **🔌 Multi-Provider LLM** | Ollama (local), OpenAI, Anthropic, Gemini, Groq, OpenRouter — switch at runtime |

---

## 🏗️ Architecture

```
                        ┌──────────────┐
                        │  User Input   │
                        └──────┬───────┘
                               │
                               ▼
                     ┌─────────────────┐
                     │  Supervisor AI   │  ──  Parse NL → structured params
                     └────────┬────────┘
                              │
                              ▼
                      ┌──────────────┐
                      │ Routing AI   │  ──  Classify: standard / budget / luxury / replan
                      └──────┬───────┘
                             │
              ┌──────────────┼──────────────────┐
              │              │                   │
              ▼              ▼                   ▼
      ┌────────────┐ ┌────────────┐ ┌──────────────────┐
      │ Transit    │ │ Budget     │ │ Curator          │
      │ Agent      │ │ Agent      │ │ Agent            │
      │ (parallel) │ │ (hotel +   │ │ (activity        │
      │ weather +  │ │ allocation)│ │ selection)       │
      │ transport) │ │            │ │                  │
      └──────┬─────┘ └──────┬─────┘ └────────┬─────────┘
             │              │                 │
             └──────────────┼─────────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ Itinerary AI    │  ──  Generate day-by-day plan
                   └────────┬────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │  Critic AI   │  ──  Validate + rule checks
                    └──────┬───────┘
                           │
              ┌────────────┴────────────┐
              │                         │
         needs_replan              approved
              │                         │
              ▼                         ▼
     ┌────────────────┐           ┌──────────┐
     │ Replan AI      │           │   DONE   │
     │ (max 2 cycles) │           └──────────┘
     └───────┬────────┘
             │
             └──────────► back to Critic
```

<p align="center">
  <em>Built with <a href="https://langchain-ai.github.io/langgraph/">LangGraph StateGraph</a> — 
  deterministic nodes (budget, transit, curator) run in parallel, AI nodes stream tokens via SSE.</em>
</p>

---

## ⚡ Quick Start

### Prerequisites

- **Python 3.13+**
- **Node.js 20+**
- **Ollama** (for local LLM) → [Install Ollama](https://ollama.com/)

### 1. Clone & Install Backend

```bash
git clone https://github.com/hameed-afsar-km/TRIPZ-AI.git
cd TRIPZ-AI/backend

python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS / Linux

pip install -r requirements.txt
```

### 2. Start Ollama

```bash
ollama serve
ollama pull qwen2.5:1.5b     # default model (lightweight)
# or: ollama pull gemma2:2b  # alternative
```

### 3. Run the Backend

```bash
uvicorn main:app --reload --port 8000
```

### 4. Install & Run Frontend

```bash
cd ../frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) 🚀

> **Note:** The frontend proxies `/api/v1/*` to the backend at `localhost:8000` via Next.js rewrites.

---

## 🧠 How It Works

### The Agent Pipeline

| # | Agent | Type | Role |
|---|-------|------|------|
| 1 | **Supervisor** | 🤖 AI | Parse natural language → extract destination, origin, budget, dates, preferences |
| 2 | **Routing** | 🤖 AI | Classify trip type (standard / budget / luxury / replan) |
| 3 | **Transit** | ⚙️ Tool | Fetch live weather + mock transport costs (parallel) |
| 4 | **Budget** | ⚙️ Tool | Allocate budget: 30% transport, 35% hotels, 15% activities, 15% food, 5% buffer |
| 5 | **Curator** | ⚙️ Tool | Select activities matching budget, weather, and preferences |
| 6 | **Itinerary** | 🤖 AI | Synthesize full day-by-day itinerary with times, costs, and tips |
| 7 | **Critic** | 🤖 AI | Validate itinerary completeness & correctness |
| 8 | **Replanning** | 🤖 AI | Fix issues flagged by critic (max 2 iterations) |

### LLM Provider Support

| Provider | Models | Key Required |
|----------|--------|:---:|
| **Ollama** (local) | `qwen2.5:1.5b`, `gemma2:2b` | ❌ |
| **OpenAI** | `gpt-4o-mini` | ✅ |
| **Anthropic** | `claude-3-haiku` | ✅ |
| **Google Gemini** | `gemini-2.5-flash` | ✅ |
| **Groq** | `llama-3.3-70b` | ✅ |
| **OpenRouter** | `llama-3.1-8b` | ✅ |

> API keys are entered at runtime via the frontend settings modal (stored in `localStorage`).

### State Management

- **Session TTL**: 30 minutes (in-memory dict — swappable with Redis)
- **LLM Cache**: LRU cache (64 entries) keyed by MD5 hash of prompt
- **Streaming**: SSE events emit per-node progress + token chunks in real-time

---

## 🔧 Configuration

### Environment Variables

No `.env` file required. All configuration is handled at runtime:

- LLM provider & API keys → frontend settings modal
- Default model → `backend/main.py` (Ollama with `qwen2.5:1.5b`)
- CORS origins → `backend/main.py` (`localhost:3000`, `localhost:3001`)
- Session TTL → `backend/memory/session_memory.py` (default: 30 min)

### Frontend Proxy

`frontend/next.config.ts` rewrites `/api/v1/:path*` → `http://localhost:8000/api/v1/:path*`

---

## 📁 Project Structure

```
TRIPZ-AI/
├── backend/                        # FastAPI + LangGraph
│   ├── main.py                     # Entry point (port 8000)
│   ├── requirements.txt
│   ├── agents/                     # AI agent nodes
│   ├── api/                        # REST routers
│   ├── graphs/                     # LangGraph assembly
│   ├── models/                     # TripState TypedDict
│   ├── services/                   # LLM service layer
│   ├── tools/                      # Deterministic tools
│   └── memory/                     # Session store
├── frontend/                       # Next.js 16 app
│   ├── app/                        # Pages & layout
│   ├── components/                 # UI components
│   └── public/                     # Static assets
├── test_*.py                       # 6 test scripts
└── FIX_REPORT.md                   # Bug fix documentation
```

---

## 🧪 Testing

```bash
# From project root:
python test_supervisor.py      # AI input parsing
python test_routing.py         # Workflow classification
python test_graph.py           # Full graph execution
python test_stream.py          # Streaming events
python test_sse.py             # SSE endpoint
python test_input_parsing.py   # End-to-end parsing
```

---

## 🚀 Roadmap

- [ ] **Redis** session store for production
- [ ] **Real APIs** (Amadeus, Booking.com, Google Places)
- [ ] **User auth** + saved itineraries
- [ ] **Multi-city** trip support
- [ ] **Image generation** for destinations
- [ ] **Docker Compose** one-click deploy

---

## 🤝 Contributing

PRs are welcome! If you find a bug or have a feature idea, open an [issue](https://github.com/hameed-afsar-km/TRIPZ-AI/issues).

---

## 📄 License

[MIT](LICENSE) © 2026 Hameed Afsar KM

---

<div align="center">

**Built with ❤️ using [LangGraph](https://langchain-ai.github.io/langgraph/) + [FastAPI](https://fastapi.tiangolo.com/) + [Next.js](https://nextjs.org/)**

<br />

[![Star on GitHub](https://img.shields.io/github/stars/hameed-afsar-km/TRIPZ-AI?style=social)](https://github.com/hameed-afsar-km/TRIPZ-AI)

</div>
