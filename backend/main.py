from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from simulation import SimulationEngine


app = FastAPI(title="RPBOT Simulation Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = SimulationEngine()


class TickRequest(BaseModel):
    dt: float = Field(default=1.0, ge=0.1, le=5.0)
    steps: int = Field(default=1, ge=1, le=50)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    agent_id: str = "agent-1"
    auto_tick: bool = True


class QueueChatRequest(BaseModel):
    message: str = Field(min_length=1)
    agent_id: str = "agent-1"


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "rpbot-simulation-backend",
        "tick": engine.world.tick,
        "time": engine.world.time,
    }


@app.get("/simulation/state")
def simulation_state() -> Dict[str, Any]:
    return engine.get_state()


@app.post("/simulation/tick")
def simulation_tick(request: Optional[TickRequest] = None) -> Dict[str, Any]:
    payload = request or TickRequest()
    return engine.tick(dt=payload.dt, steps=payload.steps)


@app.post("/simulation/chat")
def simulation_chat(request: ChatRequest) -> Dict[str, Any]:
    try:
        return engine.grounded_chat(
            agent_id=request.agent_id,
            message=request.message,
            auto_tick=request.auto_tick,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/simulation/chat/queue")
def simulation_chat_queue(request: QueueChatRequest) -> Dict[str, Any]:
    try:
        engine.queue_user_chat(request.agent_id, request.message)
        return {
            "status": "queued",
            "agent_id": request.agent_id,
            "message": request.message,
            "tick": engine.world.tick,
            "time": engine.world.time,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/simulation/reset")
def simulation_reset() -> Dict[str, Any]:
    global engine
    engine = SimulationEngine()
    return {
        "status": "reset",
        "state": engine.get_state(),
    }
