from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .simulation import SimulationEngine
except ImportError:
    from simulation import SimulationEngine


app = FastAPI(title="RPBOT Simulation Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = SimulationEngine()


class TickRequest(BaseModel):
    dt: float = Field(default=1.0, ge=0.05, le=5.0)
    steps: int = Field(default=1, ge=1, le=120)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    agent_id: str = "agent-1"
    auto_tick: bool = True


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "rpbot-simulation-backend",
        "tick": engine.world.tick,
        "time": round(engine.world.time, 2),
        "agents": len(engine.world.agents),
    }


@app.get("/api/state")
def api_state() -> Dict[str, Any]:
    return engine.get_state()


@app.post("/api/tick")
def api_tick(request: Optional[TickRequest] = None) -> Dict[str, Any]:
    payload = request or TickRequest()
    return engine.tick(dt=payload.dt, steps=payload.steps)


@app.post("/api/chat")
def api_chat(request: ChatRequest) -> Dict[str, Any]:
    try:
        return engine.grounded_chat(
            agent_id=request.agent_id,
            message=request.message,
            auto_tick=request.auto_tick,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/reset")
def api_reset() -> Dict[str, Any]:
    global engine
    engine = SimulationEngine()
    return {"status": "reset", "state": engine.get_state()}


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
