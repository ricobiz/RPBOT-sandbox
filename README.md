# RPBOT Sandbox

State-driven AI sandbox prototype for experimenting with autonomous-agent loops in a web UI.

This repo is currently an MVP scaffold with:
- a Python simulation core (`backend/simulation.py`)
- a backend API (`backend/main.py`)
- an iPhone-first-style Next.js UI shell with agent/event state store (`frontend/...`)

It is designed to mirror key ideas from [`ricobiz/RPBOT-rpmodule`](https://github.com/ricobiz/RPBOT-rpmodule): structured agent state, perception limits, evolving internal condition, goal/action progression, and response grounding in simulation state.

---

## What the app is (current state)

The rebuilt project is a **realistic state-driven AI sandbox foundation** where simulation state drives what the agent can perceive, decide, do, remember, and report.

### Current MVP scene and UI

Current scene/model state is intentionally simple:
- one default scene (`default`)
- simulation state advanced in discrete ticks

Current UI (mobile/vertical-first structure):
- **3D Scene placeholder panel** (`frontend/src/app/page.tsx`)
- **Agent status panel** (`components/AgentStatus.tsx`)
- **Event timeline** (`components/EventTimeline.tsx`)
- **Bottom controls + grounded chat input** (`components/BottomControls.tsx`)
- **Global simulation state store** via Zustand (`store/useSimulationStore.ts`)

---

## Local development (minimal)

### Prerequisites

- Python 3.10+
- Node.js 18.18+
- npm

### 1) Start the backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows (PowerShell): .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend defaults:
- Base URL: `http://127.0.0.1:8000`
- Health check: `GET /health`
- Simulation state: `GET /api/state`

Optional backend env vars:
- `BACKEND_CORS_ORIGINS` (default `*`) — comma-separated list, e.g. `http://localhost:3000,http://127.0.0.1:3000`
- `PORT` for deployment platforms that inject it

Compatibility entrypoint:
- Running from repo root also works: `python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}`
- Root `main.py` re-exports the backend app from `backend/main.py`

### Railway / Nixpacks backend start command

The ASGI app object is `app` in `backend/main.py`, and it is re-exported by root `main.py`.

Use this deterministic Railway start command from the repo root:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Install backend dependencies from `backend/requirements.txt` so `uvicorn` is always available.

### 2) Start the frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Frontend defaults:
- URL: `http://localhost:3000`
- Scripts:
  - `npm run dev`
  - `npm run build`
  - `npm run start`

Optional frontend env var:
- `NEXT_PUBLIC_BACKEND_URL` — explicit backend base URL (example: `http://127.0.0.1:8000`)
- If omitted, the frontend auto-targets `localhost:8000` when running locally.

### Optional `rpmodule` integration behavior

`backend/simulation.py` attempts to load one of these optional Python modules if installed:
- `rpmodule`
- `rpbot_rpmodule`
- `RPBOT_rpmodule`

If none are available (or initialization fails), the backend uses deterministic fallback behavior so startup and API endpoints remain functional.

---

## Summary

RPBOT Sandbox is a **state-first AI simulation scaffold**: a deterministic world model + perception boundary + agent/UI state pipeline that mirrors rpmodule design intent and is ready for deeper cognition, emotion/condition dynamics, and multi-agent scenario growth.
