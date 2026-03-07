from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from .simulation import Simulation

class ActionRequest(BaseModel):
    agent_id: str
    action: str
    params: Dict[str, Any] = {}

app = FastAPI()
simulation = Simulation()

@app.get("/state")
def get_state():
    return simulation.get_state()

@app.post("/action")
def post_action(req: ActionRequest):
    try:
        simulation.apply_action(req.agent_id, req.action, req.params)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/perception/{agent_id}")
def get_perception(agent_id: str):
    perception = simulation.get_perception(agent_id)
    if not perception:
        raise HTTPException(status_code=404, detail="Agent not found")
    return perception

@app.post("/step")
def step():
    simulation.step_time()
    return {"status": "advanced"}
