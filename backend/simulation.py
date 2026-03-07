from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import importlib
from math import atan2, cos, pi, sin, sqrt
from typing import Any, Dict, List, Optional, Tuple

Vector2 = Tuple[float, float]


@dataclass
class WorldObject:
    id: str
    name: str
    kind: str
    position: Vector2
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationEvent:
    id: str
    tick: int
    time: float
    event_type: str
    source_agent_id: Optional[str]
    target_id: Optional[str]
    position: Vector2
    content: str


@dataclass
class MemoryEvent:
    id: str
    tick: int
    time: float
    category: str
    content: str
    confidence: float = 1.0


@dataclass
class EmotionalState:
    calm: float = 0.58
    engagement: float = 0.44
    anxiety: float = 0.18
    curiosity: float = 0.56
    fatigue_feel: float = 0.16


@dataclass
class PhysicalState:
    energy: float = 0.88
    stamina: float = 0.85
    hunger: float = 0.2
    stress_load: float = 0.18


@dataclass
class GoalState:
    name: str
    priority: float
    reason: str


@dataclass
class PlanState:
    steps: List[str] = field(default_factory=list)
    cursor: int = 0


@dataclass
class ActionState:
    name: str = "idle"
    status: str = "idle"
    target_id: Optional[str] = None
    target_position: Optional[Vector2] = None
    duration: float = 0.0
    elapsed: float = 0.0


@dataclass
class PerceptionResult:
    nearby_visible_objects: List[Dict[str, Any]]
    nearby_visible_agents: List[Dict[str, Any]]
    user_messages: List[str]
    recent_events: List[Dict[str, Any]]


@dataclass
class AgentState:
    id: str
    name: str
    position: Vector2
    facing_radians: float = 0.0
    walk_speed: float = 1.25
    vision_range: float = 7.5
    emotional_state: EmotionalState = field(default_factory=EmotionalState)
    physical_state: PhysicalState = field(default_factory=PhysicalState)
    current_goal: GoalState = field(default_factory=lambda: GoalState(name="idle", priority=0.1, reason="startup"))
    current_plan: PlanState = field(default_factory=PlanState)
    current_action: ActionState = field(default_factory=ActionState)
    pending_user_messages: List[str] = field(default_factory=list)
    memory: List[MemoryEvent] = field(default_factory=list)
    last_perception: Optional[PerceptionResult] = None
    last_response: str = ""


@dataclass
class WorldState:
    time: float
    tick: int
    paused: bool
    agents: Dict[str, AgentState]
    objects: Dict[str, WorldObject]
    recent_events: List[SimulationEvent] = field(default_factory=list)


class RPModuleAdapter:
    """Optional wrapper around ricobiz/RPBOT-rpmodule behavior/emotion engine."""

    def __init__(self) -> None:
        self.module = None
        self.engine = None
        self.module_name: Optional[str] = None
        self.available = False
        self._load_optional_module()

    def _load_optional_module(self) -> None:
        module_candidates = (
            "rpbot_rpmodule",
            "rpmodule",
            "RPBOT_rpmodule",
            "ricobiz.RPBOT_rpmodule",
        )
        for name in module_candidates:
            try:
                self.module = importlib.import_module(name)
                self.module_name = name
                break
            except Exception:
                continue

        if self.module is None:
            return

        for cls_name in ("BehaviorEngine", "DecisionEngine", "Engine", "RPModuleEngine"):
            cls = getattr(self.module, cls_name, None)
            if cls is None:
                continue
            try:
                self.engine = cls()
                self.available = True
                return
            except Exception:
                self.engine = None

        if any(hasattr(self.module, fn) for fn in ("evaluate", "decide", "step")):
            self.available = True

    def evaluate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.available:
            try:
                if self.engine is not None:
                    for fn_name in ("step", "evaluate", "decide"):
                        fn = getattr(self.engine, fn_name, None)
                        if callable(fn):
                            result = fn(payload)
                            if isinstance(result, dict):
                                return result

                if self.module is not None:
                    for fn_name in ("step", "evaluate", "decide"):
                        fn = getattr(self.module, fn_name, None)
                        if callable(fn):
                            result = fn(payload)
                            if isinstance(result, dict):
                                return result
            except Exception:
                pass

        interpretation = payload.get("interpretation", {})
        physical = payload.get("agent", {}).get("physical", {})
        has_user_intent = bool(interpretation.get("user_intent"))
        threat_level = _to_number(interpretation.get("threat_level"), 0.0)
        energy = _to_number(physical.get("energy"), 0.8)
        hunger = _to_number(physical.get("hunger"), 0.2)

        return {
            "emotion_delta": {
                "engagement": 0.08 if has_user_intent else 0.01,
                "anxiety": 0.08 if threat_level > 0.5 else -0.01,
                "curiosity": 0.04,
            },
            "physical_delta": {
                "stress_load": 0.03 if threat_level > 0.5 else -0.01,
                "energy": -0.01,
                "hunger": 0.015,
            },
            "goal_bias": {
                "respond_user": 0.75 if has_user_intent else 0.1,
                "rest": max(0.0, 0.4 - energy),
                "seek_food": max(0.0, hunger - 0.55),
                "patrol": 0.2,
            },
        }


class SimulationEngine:
    def __init__(self) -> None:
        self._event_counter = 0
        self._memory_counter = 0
        self.rp_adapter = RPModuleAdapter()
        self.scene_id = "default"
        self.world = self._create_initial_world()

    def _create_initial_world(self) -> WorldState:
        agent = AgentState(id="agent-1", name="Rico", position=(0.0, 0.0))
        objects = {
            "obj-console": WorldObject(
                id="obj-console",
                name="Console",
                kind="terminal",
                position=(1.4, -0.5),
                metadata={"interactable": True, "description": "Field operations terminal"},
            ),
            "obj-crate": WorldObject(
                id="obj-crate",
                name="Crate",
                kind="container",
                position=(-1.3, 1.2),
                metadata={"interactable": True, "food": True, "description": "Supply crate"},
            ),
            "obj-beacon": WorldObject(
                id="obj-beacon",
                name="Beacon",
                kind="landmark",
                position=(3.2, 2.1),
                metadata={"interactable": False, "description": "Navigation beacon"},
            ),
        }
        return WorldState(time=0.0, tick=0, paused=False, agents={agent.id: agent}, objects=objects)

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "service": "rpbot-simulation-backend",
            "tick": self.world.tick,
            "time": round(self.world.time, 3),
            "paused": self.world.paused,
            "agents": len(self.world.agents),
            "rp_module": {"available": self.rp_adapter.available, "module": self.rp_adapter.module_name},
        }

    def set_paused(self, paused: bool) -> Dict[str, Any]:
        self.world.paused = paused
        self._record_event(
            event_type="simulation_pause" if paused else "simulation_resume",
            source_agent_id=None,
            target_id=None,
            position=(0.0, 0.0),
            content="paused" if paused else "running",
        )
        return self.get_state()

    def queue_user_chat(self, agent_id: str, message: str) -> None:
        agent = self.world.agents.get(agent_id)
        if agent is None:
            raise ValueError(f"Agent '{agent_id}' not found")
        cleaned = message.strip()
        if not cleaned:
            return
        agent.pending_user_messages.append(cleaned)
        self._record_event("user_message", None, agent_id, agent.position, cleaned)

    def grounded_chat(self, agent_id: str, message: str, auto_tick: bool = True) -> Dict[str, Any]:
        self.queue_user_chat(agent_id, message)
        if auto_tick and not self.world.paused:
            tick_result = self.tick(dt=1.0, steps=1)
            response = tick_result.get("updates", [{}])[-1].get("response", "")
        else:
            response = self.world.agents[agent_id].last_response

        return {"status": "ok", "response": response, "state": self.get_state()}

    def tick(self, dt: float = 1.0, steps: int = 1) -> Dict[str, Any]:
        dt = max(0.05, min(dt, 5.0))
        steps = max(1, min(steps, 120))
        updates: List[Dict[str, Any]] = []

        if self.world.paused:
            return {"status": "ok", "tick": self.world.tick, "time": round(self.world.time, 3), "steps": 0, "updates": updates, "state": self.get_state()}

        for _ in range(steps):
            self.world.tick += 1
            self.world.time += dt

            for agent in self.world.agents.values():
                perception = self._perceive(agent)
                interpretation = self._interpret(perception)
                rp_result = self.rp_adapter.evaluate(
                    {
                        "world": {"tick": self.world.tick, "time": self.world.time, "scene_id": self.scene_id},
                        "agent": {
                            "id": agent.id,
                            "name": agent.name,
                            "position": agent.position,
                            "emotion": vars(agent.emotional_state),
                            "physical": vars(agent.physical_state),
                        },
                        "perception": self._serialize_perception(perception),
                        "interpretation": interpretation,
                    }
                )

                self._apply_rp_output(agent, rp_result, dt)
                goal = self._select_goal(agent, perception, interpretation, rp_result)
                plan = self._plan(agent, goal)
                action_summary = self._act(agent, dt)
                response = self._respond(agent, perception, interpretation, rp_result)
                self._update_memory(agent, goal, plan, action_summary, response)

                updates.append(
                    {
                        "tick": self.world.tick,
                        "agent_id": agent.id,
                        "goal": {"name": goal.name, "priority": goal.priority, "reason": goal.reason},
                        "action": self._serialize_action(agent.current_action),
                        "response": response,
                    }
                )

        return {
            "status": "ok",
            "tick": self.world.tick,
            "time": round(self.world.time, 3),
            "steps": steps,
            "updates": updates,
            "state": self.get_state(),
        }

    def get_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        capped = max(1, min(limit, 500))
        return [self._serialize_event(e) for e in self.world.recent_events[-capped:]]

    def get_timeline(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [
            {
                "id": event["id"],
                "tick": event["tick"],
                "timestamp": event["timestamp"],
                "category": event["event_type"],
                "content": event["content"],
                "source_agent_id": event.get("source_agent_id"),
            }
            for event in self.get_events(limit)
        ]

    def get_state(self) -> Dict[str, Any]:
        return {
            "tick": self.world.tick,
            "time": round(self.world.time, 3),
            "paused": self.world.paused,
            "scene_id": self.scene_id,
            "agents": {agent_id: self._serialize_agent(a) for agent_id, a in self.world.agents.items()},
            "objects": {object_id: self._serialize_object(o) for object_id, o in self.world.objects.items()},
            "perceptions": {agent_id: self._serialize_perception(a.last_perception) for agent_id, a in self.world.agents.items()},
            "events": self.get_events(120),
            "timeline": self.get_timeline(120),
        }

    def _perceive(self, agent: AgentState) -> PerceptionResult:
        visible_objects: List[Dict[str, Any]] = []
        for obj in self.world.objects.values():
            dist = _distance(agent.position, obj.position)
            if dist <= agent.vision_range:
                visible_objects.append(
                    {
                        "id": obj.id,
                        "name": obj.name,
                        "kind": obj.kind,
                        "position": [obj.position[0], obj.position[1]],
                        "distance": round(dist, 3),
                        "interactable": bool(obj.metadata.get("interactable")),
                    }
                )

        visible_agents: List[Dict[str, Any]] = []
        for other in self.world.agents.values():
            if other.id == agent.id:
                continue
            dist = _distance(agent.position, other.position)
            if dist <= agent.vision_range:
                visible_agents.append(
                    {"id": other.id, "name": other.name, "position": [other.position[0], other.position[1]], "distance": round(dist, 3)}
                )

        recent_events = [
            self._serialize_event(event)
            for event in self.world.recent_events[-12:]
            if event.source_agent_id == agent.id or event.target_id in (agent.id, None)
        ]

        perception = PerceptionResult(
            nearby_visible_objects=visible_objects,
            nearby_visible_agents=visible_agents,
            user_messages=list(agent.pending_user_messages),
            recent_events=recent_events,
        )
        agent.last_perception = perception
        return perception

    def _interpret(self, perception: PerceptionResult) -> Dict[str, Any]:
        text = " ".join(perception.user_messages).lower()
        threat_level = 0.0
        for token in ("danger", "urgent", "alert", "help", "threat"):
            if token in text:
                threat_level += 0.2

        user_intent: Optional[str] = None
        if text:
            if any(word in text for word in ("move", "go", "walk")):
                user_intent = "move"
            elif any(word in text for word in ("status", "how are", "state")):
                user_intent = "status"
            elif any(word in text for word in ("eat", "food", "crate")):
                user_intent = "seek_food"
            else:
                user_intent = "chat"

        return {
            "user_intent": user_intent,
            "threat_level": _clamp(threat_level, 0.0, 1.0),
            "has_user_messages": bool(perception.user_messages),
            "visible_objects": len(perception.nearby_visible_objects),
        }

    def _apply_rp_output(self, agent: AgentState, rp_result: Dict[str, Any], dt: float) -> None:
        for key, value in (rp_result.get("emotion_delta") or rp_result.get("emotional_delta") or {}).items():
            if hasattr(agent.emotional_state, key):
                setattr(agent.emotional_state, key, _clamp(getattr(agent.emotional_state, key) + _to_number(value, 0.0) * dt))

        for key, value in (rp_result.get("physical_delta") or {}).items():
            if hasattr(agent.physical_state, key):
                setattr(agent.physical_state, key, _clamp(getattr(agent.physical_state, key) + _to_number(value, 0.0) * dt))

        agent.physical_state.energy = _clamp(agent.physical_state.energy - (0.005 * dt))
        agent.physical_state.stamina = _clamp(agent.physical_state.stamina - (0.004 * dt))
        agent.physical_state.hunger = _clamp(agent.physical_state.hunger + (0.008 * dt))
        agent.physical_state.stress_load = _clamp(agent.physical_state.stress_load + (0.002 * dt))
        agent.emotional_state.fatigue_feel = _clamp(1.0 - agent.physical_state.energy)

    def _select_goal(
        self,
        agent: AgentState,
        perception: PerceptionResult,
        interpretation: Dict[str, Any],
        rp_result: Dict[str, Any],
    ) -> GoalState:
        bias = rp_result.get("goal_bias") or {}
        scores = {
            "respond_user": _to_number(bias.get("respond_user"), 0.0) + (0.65 if interpretation.get("has_user_messages") else 0.0),
            "seek_food": _to_number(bias.get("seek_food"), 0.0) + max(0.0, agent.physical_state.hunger - 0.58),
            "rest": _to_number(bias.get("rest"), 0.0) + max(0.0, 0.45 - agent.physical_state.energy),
            "patrol": _to_number(bias.get("patrol"), 0.15),
        }
        if perception.nearby_visible_objects:
            scores["patrol"] += 0.1

        goal_name = max(scores, key=scores.get)
        reason = {
            "respond_user": "Pending user input",
            "seek_food": "Hunger above comfort threshold",
            "rest": "Energy conservation",
            "patrol": "Routine environment scan",
        }[goal_name]
        agent.current_goal = GoalState(name=goal_name, priority=_clamp(scores[goal_name]), reason=reason)
        return agent.current_goal

    def _plan(self, agent: AgentState, goal: GoalState) -> PlanState:
        if goal.name == "respond_user":
            steps = ["orient-to-user", "compose-grounded-response", "deliver-response"]
            action = ActionState(name="orient", status="running", duration=0.8)
        elif goal.name == "seek_food":
            target = self.world.objects["obj-crate"].position if "obj-crate" in self.world.objects else self._patrol_target()
            steps = ["navigate-to-food-source", "interact", "recover"]
            action = ActionState(name="walk", status="running", target_id="obj-crate", target_position=target, duration=3.0)
        elif goal.name == "rest":
            steps = ["reduce-activity", "stabilize-state"]
            action = ActionState(name="idle", status="running", duration=1.5)
        else:
            target = self._patrol_target()
            steps = ["scan-nearby", "reposition", "observe"]
            action = ActionState(name="walk", status="running", target_position=target, duration=2.2)

        agent.current_plan = PlanState(steps=steps, cursor=0)
        agent.current_action = action
        return agent.current_plan

    def _act(self, agent: AgentState, dt: float) -> Dict[str, Any]:
        action = agent.current_action
        action.elapsed = min(action.duration if action.duration > 0 else dt, action.elapsed + dt)
        moved = False

        if action.name == "walk" and action.target_position is not None:
            moved = self._move_toward(agent, action.target_position, dt)
            if moved:
                self._record_event("move", agent.id, action.target_id, agent.position, f"{agent.name} moved toward target")

        if action.elapsed >= max(0.1, action.duration):
            action.status = "done"

        return {"name": action.name, "status": action.status, "moved": moved, "position": [agent.position[0], agent.position[1]]}

    def _respond(
        self,
        agent: AgentState,
        perception: PerceptionResult,
        interpretation: Dict[str, Any],
        rp_result: Dict[str, Any],
    ) -> str:
        explicit = rp_result.get("response")
        if isinstance(explicit, str) and explicit.strip():
            text = explicit.strip()
        elif perception.user_messages:
            msg = perception.user_messages[-1]
            nearby = ", ".join(obj["name"] for obj in perception.nearby_visible_objects[:3]) or "nothing notable"
            text = f"I heard: '{msg}'. Current goal: {agent.current_goal.name}. Nearby: {nearby}."
        elif interpretation.get("threat_level", 0.0) > 0.5:
            text = "Alert: elevated threat cues detected. Staying vigilant."
        else:
            text = "Maintaining patrol and monitoring surroundings."

        if text != agent.last_response:
            self._record_event("agent_response", agent.id, None, agent.position, text)

        agent.last_response = text
        agent.pending_user_messages.clear()
        return text

    def _update_memory(self, agent: AgentState, goal: GoalState, plan: PlanState, action_summary: Dict[str, Any], response: str) -> None:
        content = (
            f"goal={goal.name} priority={goal.priority:.2f}; "
            f"plan_step={plan.steps[0] if plan.steps else 'none'}; "
            f"action={action_summary.get('name')} status={action_summary.get('status')}; "
            f"response={response[:80]}"
        )
        agent.memory.append(
            MemoryEvent(
                id=self._next_memory_id(),
                tick=self.world.tick,
                time=self.world.time,
                category="decision",
                content=content,
                confidence=0.9,
            )
        )
        if len(agent.memory) > 120:
            agent.memory = agent.memory[-120:]

    def _move_toward(self, agent: AgentState, target: Vector2, dt: float) -> bool:
        dx = target[0] - agent.position[0]
        dy = target[1] - agent.position[1]
        distance = sqrt((dx * dx) + (dy * dy))
        if distance <= 0.02:
            return False
        step = min(distance, agent.walk_speed * dt)
        nx = agent.position[0] + (dx / distance) * step
        ny = agent.position[1] + (dy / distance) * step
        agent.position = (round(nx, 4), round(ny, 4))
        agent.facing_radians = atan2(dy, dx)
        return True

    def _patrol_target(self) -> Vector2:
        radius = 2.8
        angle = (self.world.time * 0.35) % (2 * pi)
        return (round(cos(angle) * radius, 4), round(sin(angle) * radius, 4))

    def _record_event(self, event_type: str, source_agent_id: Optional[str], target_id: Optional[str], position: Vector2, content: str) -> None:
        self.world.recent_events.append(
            SimulationEvent(
                id=self._next_event_id(),
                tick=self.world.tick,
                time=self.world.time,
                event_type=event_type,
                source_agent_id=source_agent_id,
                target_id=target_id,
                position=position,
                content=content,
            )
        )
        if len(self.world.recent_events) > 500:
            self.world.recent_events = self.world.recent_events[-500:]

    def _serialize_agent(self, agent: AgentState) -> Dict[str, Any]:
        return {
            "id": agent.id,
            "name": agent.name,
            "position": [round(agent.position[0], 4), round(agent.position[1], 4)],
            "facing_radians": round(agent.facing_radians, 4),
            "emotional_state": {
                "calm": {"intensity": round(agent.emotional_state.calm, 4)},
                "engagement": {"intensity": round(agent.emotional_state.engagement, 4)},
                "anxiety": {"intensity": round(agent.emotional_state.anxiety, 4)},
                "curiosity": {"intensity": round(agent.emotional_state.curiosity, 4)},
                "fatigue_feel": {"intensity": round(agent.emotional_state.fatigue_feel, 4)},
            },
            "physical_state": {
                "energy": round(agent.physical_state.energy, 4),
                "stamina": round(agent.physical_state.stamina, 4),
                "hunger": round(agent.physical_state.hunger, 4),
                "stress_load": round(agent.physical_state.stress_load, 4),
            },
            "current_goal": {"name": agent.current_goal.name, "priority": round(agent.current_goal.priority, 4), "reason": agent.current_goal.reason},
            "current_plan": {"steps": list(agent.current_plan.steps), "cursor": agent.current_plan.cursor},
            "current_action": self._serialize_action(agent.current_action),
            "last_response": agent.last_response,
            "memory": [
                {
                    "id": m.id,
                    "tick": m.tick,
                    "time": round(m.time, 3),
                    "timestamp": _iso_from_seconds(m.time),
                    "category": m.category,
                    "content": m.content,
                    "confidence": round(m.confidence, 3),
                }
                for m in agent.memory[-30:]
            ],
        }

    def _serialize_object(self, obj: WorldObject) -> Dict[str, Any]:
        payload = {"id": obj.id, "name": obj.name, "kind": obj.kind, "position": [round(obj.position[0], 4), round(obj.position[1], 4)]}
        payload.update(obj.metadata)
        return payload

    def _serialize_action(self, action: ActionState) -> Dict[str, Any]:
        return {
            "name": action.name,
            "status": action.status,
            "target_id": action.target_id,
            "target_position": [action.target_position[0], action.target_position[1]] if action.target_position else None,
            "duration": round(action.duration, 3),
            "elapsed": round(action.elapsed, 3),
        }

    def _serialize_perception(self, perception: Optional[PerceptionResult]) -> Dict[str, Any]:
        if perception is None:
            return {"nearby_visible_objects": [], "nearby_visible_agents": [], "user_messages": [], "recent_events": []}
        return {
            "nearby_visible_objects": perception.nearby_visible_objects,
            "nearby_visible_agents": perception.nearby_visible_agents,
            "user_messages": perception.user_messages,
            "recent_events": perception.recent_events,
        }

    def _serialize_event(self, event: SimulationEvent) -> Dict[str, Any]:
        return {
            "id": event.id,
            "tick": event.tick,
            "time": round(event.time, 3),
            "timestamp": _iso_from_seconds(event.time),
            "event_type": event.event_type,
            "category": event.event_type,
            "source_agent_id": event.source_agent_id,
            "target_id": event.target_id,
            "position": [round(event.position[0], 4), round(event.position[1], 4)],
            "content": event.content,
        }

    def _next_event_id(self) -> str:
        self._event_counter += 1
        return f"evt-{self._event_counter:06d}"

    def _next_memory_id(self) -> str:
        self._memory_counter += 1
        return f"mem-{self._memory_counter:06d}"


def _distance(a: Vector2, b: Vector2) -> float:
    return sqrt(((a[0] - b[0]) ** 2) + ((a[1] - b[1]) ** 2))


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _to_number(value: Any, fallback: float) -> float:
    return float(value) if isinstance(value, (int, float)) else fallback


def _iso_from_seconds(seconds: float) -> str:
    base = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (base + timedelta(seconds=float(max(0.0, seconds)))).isoformat()
