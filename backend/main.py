from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

SIMULATION_IMPORT_ERROR: Optional[str] = None

try:
    from .simulation import SimulationEngine as ImportedSimulationEngine
except Exception:
    try:
        from simulation import SimulationEngine as ImportedSimulationEngine
    except Exception as exc:
        ImportedSimulationEngine = None  # type: ignore[assignment]
        SIMULATION_IMPORT_ERROR = str(exc)


class _FallbackSimulationEngine:
    """Non-crashing placeholder engine used when simulation import/init fails."""

    class _World:
        tick = 0
        time = 0.0
        agents: Dict[str, Any] = {}

    def __init__(self, reason: str) -> None:
        self._reason = reason
        self.world = self._World()

    def get_state(self) -> Dict[str, Any]:
        return {
            "status": "error",
            "integration": "unavailable",
            "error": self._reason,
            "tick": 0,
            "time": 0.0,
            "nearby_agents": {},
            "recent_events": [],
            "objects": {},
            "agents": {},
        }

    def tick(self, dt: float = 1.0, steps: int = 1) -> Dict[str, Any]:
        return {
            "status": "error",
            "integration": "unavailable",
            "error": self._reason,
            "tick": self.world.tick,
            "time": self.world.time,
            "steps": max(1, int(steps)),
            "updates": [],
            "state": self.get_state(),
        }

    def grounded_chat(self, agent_id: str, message: str, auto_tick: bool = True) -> Dict[str, Any]:
        return {
            "status": "error",
            "integration": "unavailable",
            "error": self._reason,
            "agent_id": agent_id,
            "message": message,
            "auto_tick": auto_tick,
            "active_goal": {"name": "idle", "priority": 0.0, "reason": "integration_unavailable"},
            "active_action": {
                "name": "idle",
                "status": "idle",
                "target_id": None,
                "target_position": None,
                "duration": 0.0,
                "elapsed": 0.0,
            },
            "emotion": {},
            "physical": {},
            "response": "Simulation integration unavailable.",
            "state": self.get_state(),
        }


def _build_engine() -> Any:
    if ImportedSimulationEngine is None:
        return _FallbackSimulationEngine(SIMULATION_IMPORT_ERROR or "Simulation module import failed")

    try:
        return ImportedSimulationEngine()
    except Exception as exc:
        return _FallbackSimulationEngine(f"Simulation engine initialization failed: {exc}")


app = FastAPI(title="RPBOT Simulation Backend", version="1.0.0")

cors_raw = os.getenv("BACKEND_CORS_ORIGINS", "*")
if cors_raw.strip() == "*":
    cors_origins = ["*"]
else:
    cors_origins = [origin.strip() for origin in cors_raw.split(",") if origin.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = _build_engine()


class TickRequest(BaseModel):
    dt: float = Field(default=1.0, ge=0.05, le=5.0)
    steps: int = Field(default=1, ge=1, le=120)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    agent_id: str = "agent-1"
    auto_tick: bool = True


def _safe_json_response(endpoint: str, exc: Exception) -> Dict[str, Any]:
    return {
        "status": "error",
        "endpoint": endpoint,
        "error": str(exc),
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    try:
        state = engine.get_state()
        agents = state.get("agents", {}) if isinstance(state, dict) else {}
        return {
            "status": "ok" if not isinstance(state, dict) or state.get("status") != "error" else "degraded",
            "service": "rpbot-simulation-backend",
            "tick": state.get("tick", getattr(getattr(engine, "world", object()), "tick", 0)) if isinstance(state, dict) else 0,
            "time": state.get("time", round(getattr(getattr(engine, "world", object()), "time", 0.0), 2)) if isinstance(state, dict) else 0.0,
            "agents": len(agents) if isinstance(agents, dict) else 0,
            "integration": "available" if not isinstance(state, dict) or state.get("status") != "error" else "unavailable",
        }
    except Exception as exc:
        return {
            "status": "error",
            "service": "rpbot-simulation-backend",
            "tick": 0,
            "time": 0.0,
            "agents": 0,
            "integration": "unavailable",
            "error": str(exc),
        }


@app.get("/api/state")
def api_state() -> Dict[str, Any]:
    try:
        state = engine.get_state()
        if isinstance(state, dict):
            return state
        return {"status": "error", "error": "Invalid state response"}
    except Exception as exc:
        return _safe_json_response("state", exc)


@app.post("/api/tick")
def api_tick(request: Optional[TickRequest] = None) -> Dict[str, Any]:
    payload = request or TickRequest()
    try:
        result = engine.tick(dt=payload.dt, steps=payload.steps)
        if isinstance(result, dict):
            return result
        return {"status": "error", "error": "Invalid tick response", "updates": []}
    except Exception as exc:
        return {
            **_safe_json_response("tick", exc),
            "tick": 0,
            "time": 0.0,
            "steps": payload.steps,
            "updates": [],
        }


@app.post("/api/chat")
def api_chat(request: ChatRequest) -> Dict[str, Any]:
    try:
        result = engine.grounded_chat(
            agent_id=request.agent_id,
            message=request.message,
            auto_tick=request.auto_tick,
        )
        if isinstance(result, dict):
            return result
        return {"status": "error", "error": "Invalid chat response", "response": ""}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        return {
            **_safe_json_response("chat", exc),
            "agent_id": request.agent_id,
            "message": request.message,
            "response": "",
        }


@app.post("/api/reset")
def api_reset() -> Dict[str, Any]:
    global engine
    try:
        engine = _build_engine()
        return {"status": "reset", "state": engine.get_state()}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "state": {}}


# Backward-compatible aliases
@app.get("/simulation/state")
def simulation_state() -> Dict[str, Any]:
    return api_state()


@app.post("/simulation/tick")
def simulation_tick(request: Optional[TickRequest] = None) -> Dict[str, Any]:
    return api_tick(request)


@app.post("/simulation/chat")
def simulation_chat(request: ChatRequest) -> Dict[str, Any]:
    return api_chat(request)


@app.post("/simulation/reset")
def simulation_reset() -> Dict[str, Any]:
    return api_reset()
