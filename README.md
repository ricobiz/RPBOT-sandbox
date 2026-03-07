# RPBOT Sandbox

State-driven AI sandbox prototype for experimenting with autonomous-agent loops in a web UI.

This repo is currently an MVP scaffold with:
- a Python simulation core (`backend/simulation.py`)
- a lightweight backend entry placeholder (`backend/main.py`)
- an iPhone-first-style Next.js UI shell with agent/event state store (`frontend/...`)

It is designed to mirror key ideas from [`ricobiz/RPBOT-rpmodule`](https://github.com/ricobiz/RPBOT-rpmodule): structured agent state, perception limits, evolving internal condition, goal/action progression, and response grounding in simulation state.

---

## What the app is (current state)

The rebuilt project is a **realistic state-driven AI sandbox foundation** where simulation state drives what the agent can perceive, decide, do, remember, and report.

### Current MVP scene and UI

Current scene/model state is intentionally simple:
- one default scene (`default`)
- one `robot` object with position + velocity
- time advancing in discrete ticks (`step_time()`)

Current UI (mobile/vertical-first structure):
- **3D Scene placeholder panel** (`frontend/src/app/page.tsx`)
- **Agent status bar placeholder** (`page.tsx`) plus reusable richer status component (`components/AgentStatus.tsx`)
- **Event timeline placeholder** (`page.tsx`) plus reusable event component (`components/EventTimeline.tsx`)
- **Bottom controls + chat input + action sheets** (`components/BottomControls.tsx`)
- **Global simulation state store** via Zustand (`store/useSimulationStore.ts`)

---

## Architecture modules

The architecture is organized around modules that can be expanded into full multi-agent simulation behavior.

1. **World State**  
   Implemented in `backend/simulation.py`:
   - scenes
   - objects
   - obstacles
   - simulation clock

2. **Perception (non-omniscient model)**  
   `Simulation.get_perception()` returns a **local view** for the robot (robot position + nearby objects), not full world internals. This is the basis for non-omniscient behavior.

3. **Memory**  
   Frontend event logs (`events` in Zustand) already act as short-horizon trace memory. Backend long-term episodic/semantic memory modules are planned extension points.

4. **Goals**  
   The store includes explicit `goal` state for the agent. Goal policies are currently UI/state-level and ready for backend planner integration.

5. **Action Execution**  
   `Simulation.apply_action()` currently supports movement actions by updating robot velocity. `Scene.step()` + `Object.update()` execute state transitions over time.

6. **Agent State**  
   Store tracks:
   - `goal`
   - `action`
   - `emotionalState`
   - `isThinking`
   - `isMoving`

7. **Simulation Tick / Time Progression**  
   `step_time()` advances time in discrete ticks (`dt = 1.0`) and updates all scene objects.

8. **Chat Grounding**  
   Chat input exists in `BottomControls`. Grounding target is the same shared simulation/agent state (world, events, goals, condition), so chat can be constrained by what the agent actually knows.

9. **UI State**  
   Zustand central store (`useSimulationStore`) provides deterministic, inspectable UI state transitions for agent status, world objects, and event timeline.

---

## Core loop (target behavior, partially implemented)

The intended loop (already scaffolded in data structures and simulation timing) is:

**perception → interpretation → emotional/physical update → goal selection → plan/action selection → execution → memory update → response generation**

How this maps today:
- **Perception**: `get_perception()`
- **Interpretation**: currently minimal/manual (extension point for planner/reasoner)
- **Emotional/physical update**: represented in agent state fields, with tick hook available in `step_time()`
- **Goal selection**: `goal` state exists; policy wiring pending
- **Plan/action selection**: currently simple action dispatch (`apply_action`)
- **Execution**: object motion in `update()`/`step()`
- **Memory update**: event timeline/store updates
- **Response generation**: chat/UI response path scaffolded in controls + status/timeline components

---

## Relation to `RPBOT-rpmodule` concepts

This sandbox integrates/mirrors rpmodule concepts in a staged way:

- **Dynamic emotions**: represented via `emotionalState` in agent state (UI-visible now; decision-coupled logic planned).
- **Decay / update logic**: simulation tick (`step_time`) provides the exact hook where emotion, urgency, fatigue, and confidence decay/recovery logic can run each tick.
- **Physical-condition influence**: world physics/state (position/velocity now; stamina/injury/load planned) is intended to feed both action choice and response tone.

In other words: the current codebase provides the structural state machine and timing hooks; deeper rpmodule-grade cognition/condition dynamics are the next layer.

---

## Observability and debugging surfaces

Current debug/observability points:
- `Simulation.get_state()` for full serializable backend world snapshot
- `Simulation.get_perception()` for agent-limited observation snapshot
- frontend event timeline store (`events`) for chronological decision/observation/result traces
- explicit status fields (`goal`, `action`, `emotionalState`, movement/thinking flags)

These surfaces are designed to make each loop phase inspectable and debuggable.

---

## Multi-agent-ready foundations

Even in MVP form, the structure is prepared for multi-agent growth:
- world state is scene/object dictionary-based
- perception API can be called per-agent
- agent state shape is separable from rendering
- event log model supports multi-source traces

Adding more agents mainly requires agent registries + per-agent perception/action channels.

---

## Planned extension points

The repo is set up to expand into:
- additional scenes and scene switching
- richer object/obstacle types
- configurable world rules and triggers
- agent-to-agent communication channels
- humanoid/character assets and animation state
- in-app scene editing tools (spawn/edit objects, author rules, save/load scenarios)

---

## Local development (minimal)

### 1) Start the backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows (PowerShell): .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend defaults:
- URL: `http://127.0.0.1:8000`
- Health: `GET /health`
- State: `GET /api/state`

Optional backend env vars:
- `BACKEND_CORS_ORIGINS` (default `*`) — comma-separated origins, e.g. `http://localhost:3000,http://127.0.0.1:3000`
- `PORT` for deployment environments that inject a port value

Root entrypoint compatibility:
- You can also run from repo root with `python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}`.
- Root `main.py` re-exports the backend app from `backend/main.py`.

### 2) Start the frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Frontend defaults:
- URL: `http://localhost:3000`
- Scripts:
  - `npm run dev` (local dev server on port 3000)
  - `npm run build`
  - `npm run start` (production server on port 3000)

Optional frontend env var:
- `NEXT_PUBLIC_BACKEND_URL` — explicit backend base URL (example: `http://127.0.0.1:8000`)
  - If not set, the app auto-targets `localhost:8000` when running locally.

### Optional `rpmodule` integration behavior

`backend/simulation.py` attempts to load one of these optional Python modules if installed:
- `rpmodule`
- `rpbot_rpmodule`
- `RPBOT_rpmodule`

If none are available (or initialization fails), the backend runs with deterministic fallback behavior so the app still starts and endpoints remain usable.

---

## Summary

RPBOT Sandbox is now a **state-first AI simulation scaffold**: a deterministic world model + perception boundary + agent/UI state pipeline that mirrors rpmodule design intent and is ready for deeper cognition, emotion/condition dynamics, and multi-agent scenario growth.
