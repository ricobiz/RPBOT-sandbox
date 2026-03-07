"""Simulation engine for RPBOT.

This module provides a very small, illustrative simulation that keeps
track of a world state.  The state is represented as a dictionary that
contains a list of scenes, each scene containing objects and obstacles.
Time is advanced in discrete steps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class Object:
    id: str
    type: str
    position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    velocity: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])

    def update(self, dt: float) -> None:
        """Move the object according to its velocity."""
        self.position = [p + v * dt for p, v in zip(self.position, self.velocity)]


@dataclass
class Scene:
    id: str
    objects: Dict[str, Object] = field(default_factory=dict)
    obstacles: List[Any] = field(default_factory=list)

    def step(self, dt: float) -> None:
        for obj in self.objects.values():
            obj.update(dt)


class Simulation:
    def __init__(self) -> None:
        self.scenes: Dict[str, Scene] = {}
        self.time: float = 0.0
        # Create a default scene with a single object for demo purposes
        self.scenes["default"] = Scene(id="default")
        self.scenes["default"].objects["robot"] = Object(id="robot", type="robot")

    def get_state(self) -> Dict[str, Any]:
        """Return a serialisable representation of the simulation state."""
        state = {
            "time": self.time,
            "scenes": {
                scene_id: {
                    "objects": {
                        obj_id: {
                            "type": obj.type,
                            "position": obj.position,
                            "velocity": obj.velocity,
                        }
                        for obj_id, obj in scene.objects.items()
                    },
                    "obstacles": scene.obstacles,
                }
                for scene_id, scene in self.scenes.items()
            },
        }
        return state

    def apply_action(self, action: str, params: Dict[str, Any]) -> None:
        """Apply a simple action to the robot.

        Supported actions:
        - "move": sets the robot velocity.
        """
        robot = self.scenes["default"].objects.get("robot")
        if not robot:
            raise ValueError("Robot not found in simulation")
        if action == "move":
            vx = params.get("vx", 0.0)
            vy = params.get("vy", 0.0)
            vz = params.get("vz", 0.0)
            robot.velocity = [vx, vy, vz]
        else:
            raise ValueError(f"Unknown action {action}")

    def step_time(self) -> None:
        """Advance the simulation by one time step."""
        dt = 1.0
        self.time += dt
        for scene in self.scenes.values():
            scene.step(dt)

    def get_perception(self) -> Dict[str, Any]:
        """Return a simple perception of nearby objects.

        For demo purposes we just return the robot's current position and
        the positions of all other objects in the same scene.
        """
        robot = self.scenes["default"].objects.get("robot")
        if not robot:
            return {}
        perception = {
            "robot_position": robot.position,
            "nearby_objects": [
                {
                    "id": obj.id,
                    "type": obj.type,
                    "position": obj.position,
                }
                for obj_id, obj in self.scenes["default"].objects.items()
                if obj_id != "robot"
            ],
        }
        return perception

# End of simulation.py
