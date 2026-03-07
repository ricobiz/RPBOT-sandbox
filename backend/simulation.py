"""Simulation engine for RPBOT.

This module provides a small simulation that keeps track of a world state.
The state is represented as a dictionary that contains a list of scenes,
each scene containing agents and obstacles. Time is advanced in discrete steps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class Agent:
    id: str
    type: str
    position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    velocity: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    emotions: Dict[str, float] = field(default_factory=lambda: {"joy":0.0,"sadness":0.0,"anger":0.0,"fear":0.0})
    physical: Dict[str, float] = field(default_factory=lambda: {"energy":1.0,"hunger":0.0})
    goal: str = ""

    def update(self, dt: float) -> None:
        """Update agent state: move, decay emotions, update physical."""
        # Move
        self.position = [p + v * dt for p, v in zip(self.position, self.velocity)]
        # Decay emotions
        decay_rate = 0.01
        for k in self.emotions:
            self.emotions[k] = max(0.0, self.emotions[k] - decay_rate * dt)
        # Update physical: simple energy consumption
        energy_consumption = 0.005 * dt
        self.physical["energy"] = max(0.0, self.physical["energy"] - energy_consumption)
        # Hunger increases
        hunger_increase = 0.002 * dt
        self.physical["hunger"] = min(1.0, self.physical["hunger"] + hunger_increase)


@dataclass
class Scene:
    id: str
    agents: Dict[str, Agent] = field(default_factory=dict)
    obstacles: List[Any] = field(default_factory=list)

    def step(self, dt: float) -> None:
        for agent in self.agents.values():
            agent.update(dt)


class Simulation:
    def __init__(self) -> None:
        self.scenes: Dict[str, Scene] = {}
        self.time: float = 0.0
        # Create a default scene with two agents for demo purposes
        self.scenes["default"] = Scene(id="default")
        self.scenes["default"].agents["robot"] = Agent(id="robot", type="robot")
        self.scenes["default"].agents["npc"] = Agent(id="npc", type="npc")

    def get_state(self) -> Dict[str, Any]:
        """Return a serialisable representation of the simulation state."""
        state = {
            "time": self.time,
            "scenes": {
                scene_id: {
                    "agents": {
                        agent_id: {
                            "type": agent.type,
                            "position": agent.position,
                            "velocity": agent.velocity,
                            "emotions": agent.emotions,
                            "physical": agent.physical,
                            "goal": agent.goal,
                        }
                        for agent_id, agent in scene.agents.items()
                    },
                    "obstacles": scene.obstacles,
                }
                for scene_id, scene in self.scenes.items()
            },
        }
        return state

    def apply_action(self, agent_id: str, action: str, params: Dict[str, Any]) -> None:
        """Apply a simple action to the specified agent.

        Supported actions:
        - "move": sets the agent velocity.
        """
        agent = None
        for scene in self.scenes.values():
            if agent_id in scene.agents:
                agent = scene.agents[agent_id]
                break
        if not agent:
            raise ValueError(f"Agent {agent_id} not found in simulation")
        if action == "move":
            vx = params.get("vx", 0.0)
            vy = params.get("vy", 0.0)
            vz = params.get("vz", 0.0)
            agent.velocity = [vx, vy, vz]
        else:
            raise ValueError(f"Unknown action {action}")

    def step_time(self) -> None:
        """Advance the simulation by one time step."""
        dt = 1.0
        self.time += dt
        for scene in self.scenes.values():
            scene.step(dt)

    def get_perception(self, agent_id: str) -> Dict[str, Any]:
        """Return a perception of nearby agents for the specified agent."""
        agent = None
        for scene in self.scenes.values():
            if agent_id in scene.agents:
                agent = scene.agents[agent_id]
                break
        if not agent:
            return {}
        perception = {
            "agent_position": agent.position,
            "nearby_agents": [
                {
                    "id": other.id,
                    "type": other.type,
                    "position": other.position,
                }
                for other_id, other in scene.agents.items()
                if other_id != agent_id
            ],
        }
        return perception

# End of simulation.py