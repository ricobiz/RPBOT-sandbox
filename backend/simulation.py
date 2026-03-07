from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, cos, pi, sin, sqrt
import importlib
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
class Obstacle:
    id: str
    kind: str
    position: Vector2
    radius: float


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
    confidence: float
    related_ids: List[str] = field(default_factory=list)


@dataclass
class EmotionalState:
    calm: float = 0.55
    engagement: float = 0.45
    anxiety: float = 0.20
    curiosity: float = 0.55
    fatigue_feel: float = 0.20


@dataclass
class PhysicalState:
    energy: float = 0.85
    stamina: float = 0.85
    hunger: float = 0.20
    stress: float = 0.20


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
    visible_objects: List[Dict[str, Any]]
    visible_agents: List[Dict[str, Any]]
    nearby_agents: List[Dict[str, Any]]
    recent_events: List[Dict[str, Any]]
    user_messages: List[str]
    remembered: List[Dict[str, Any]]


@dataclass
class AgentState:
    id: str
    name: str
    position: Vector2
    facing_radians: float = 0.0
    walk_speed: float = 1.2
    vision_range: float = 7.0
    fov_radians: float = pi * 0.95
    emotional_state: EmotionalState = field(default_factory=EmotionalState)
    physical_state: PhysicalState = field(default_factory=PhysicalState)
    memory: List[MemoryEvent] = field(default_factory=list)
    pending_user_messages: List[str] = field(default_factory=list)
    current_goal: GoalState = field(default_factory=lambda: GoalState(name="idle", priority=0.1, reason="startup"))
    current_plan: PlanState = field(default_factory=PlanState)
    current_action: ActionState = field(default_factory=ActionState)
    last_perception: Optional[PerceptionResult] = None
    last_interpretation: Dict[str, Any] = field(default_factory=dict)
    last_response: str = ""


@dataclass
class WorldState:
    time: float
    tick: int
    agents: Dict[str, AgentState]
    objects: Dict[str, WorldObject]
    obstacles: List[Obstacle] = field(default_factory=list)
    recent_events: List[SimulationEvent] = field(default_factory=list)
    nearby_agents: Dict[str, List[str]] = field(default_factory=dict)


class BehaviorAdapter:
    """Safe adapter to optional external behavior module.

    If an external module is importable, this adapter attempts to call a known
    behavior function. Otherwise it provides deterministic local outputs.
    """

    def __init__(self) -> None:
        self.module = None
        self.engine = None
        for module_name in ("rpmodule", "rpbot_rpmodule", "RPBOT_rpmodule"):
            try:
                self.module = importlib.import_module(module_name)
                break
            except Exception:
                continue

        if self.module is not None:
            for class_name in ("BehaviorEngine", "DecisionEngine", "Engine"):
                cls = getattr(self.module, class_name, None)
                if cls is not None:
                    try:
                        self.engine = cls()
                        break
                    except Exception:
                        self.engine = None

    def evaluate(
        self,
        agent: AgentState,
        perception: PerceptionResult,
        interpretation: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = {
            "agent": {
                "id": agent.id,
                "position": agent.position,
                "emotion": vars(agent.emotional_state),
                "physical": vars(agent.physical_state),
            },
            "perception": {
                "objects": perception.visible_objects,
                "agents": perception.visible_agents,
                "events": perception.recent_events,
                "user_messages": perception.user_messages,
            },
            "interpretation": interpretation,
        }

        try:
            if self.engine is not None and hasattr(self.engine, "evaluate"):
                result = self.engine.evaluate(payload)  # type: ignore[attr-defined]
                if isinstance(result, dict):
                    return result
            if self.module is not None and hasattr(self.module, "evaluate"):
                result = self.module.evaluate(payload)  # type: ignore[attr-defined]
                if isinstance(result, dict):
                    return result
            if self.module is not None and hasattr(self.module, "decide"):
                result = self.module.decide(payload)  # type: ignore[attr-defined]
                if isinstance(result, dict):
                    return result
        except Exception:
            pass

        urgency = 0.0
        urgency += 0.55 if interpretation.get("user_intent") else 0.0
        urgency += max(0.0, 0.4 - agent.physical_state.energy)
        urgency += max(0.0, agent.physical_state.hunger - 0.6)

        return {
            "emotion_delta": {
                "engagement": 0.08 if interpretation.get("user_intent") else 0.0,
                "anxiety": 0.08 if interpretation.get("threat_level", 0.0) > 0.45 else 0.0,
                "curiosity": 0.05 if perception.visible_objects else 0.0,
            },
            "physical_delta": {
                "stress": 0.05 if interpretation.get("threat_level", 0.0) > 0.45 else -0.01,
            },
            "goal_bias": {
                "respond_user": urgency,
                "rest": max(0.0, 0.45 - agent.physical_state.energy),
            },
        }


class SimulationEngine:
    def __init__(self) -> None:
        self._event_counter = 0
        self._memory_counter = 0
        self.behavior_adapter = BehaviorAdapter()
        self.world = self._create_initial_world()

    def _create_initial_world(self) -> WorldState:
        demo_agent = AgentState(id="agent-1", name="Rico", position=(0.0, 0.0))
        objects = {
            "obj-tree": WorldObject(
                id="obj-tree",
                name="Oak Tree",
                kind="landmark",
                position=(4.5, 2.0),
                metadata={"description": "A large old oak.", "interactable": False},
            ),
            "obj-water": WorldObject(
                id="obj-water",
                name="Water Pump",
                kind="resource",
                position=(-3.0, 1.5),
                metadata={"description": "Potable water source.", "interactable": True},
            ),
            "obj-food": WorldObject(
                id="obj-food",
                name="Supply Crate",
                kind="resource",
                position=(2.5, -4.0),
                metadata={"description": "Contains emergency rations.", "interactable": True, "food": True},
            ),
        }
        obstacles = [
            Obstacle(id="obs-rock", kind="rock", position=(1.2, 0.9), radius=0.7),
        ]
        return WorldState(
            time=0.0,
            tick=0,
            agents={demo_agent.id: demo_agent},
            objects=objects,
            obstacles=obstacles,
            nearby_agents={demo_agent.id: []},
            recent_events=[],
        )

    def queue_user_chat(self, agent_id: str, message: str) -> None:
        agent = self.world.agents.get(agent_id)
        if agent is None:
            raise ValueError(f"Agent '{agent_id}' not found")
        cleaned = message.strip()
        if not cleaned:
            return
        agent.pending_user_messages.append(cleaned)
        self._record_event(
            event_type="user_message",
            source_agent_id=None,
            target_id=agent_id,
            position=agent.position,
            content=cleaned,
        )

    def tick(self, dt: float = 1.0, steps: int = 1) -> Dict[str, Any]:
        dt = max(0.05, min(dt, 5.0))
        steps = max(1, min(steps, 120))
        step_summaries: List[Dict[str, Any]] = []

        for _ in range(steps):
            self.world.tick += 1
            self.world.time += dt
            self._refresh_nearby_agents()

            for agent_id, agent in self.world.agents.items():
                perception = self._perceive(agent)
                interpretation = self._interpret(agent, perception)
                self._update_emotional_physical(agent, perception, interpretation, dt)
                goal = self._select_goal(agent, perception, interpretation)
                plan = self._plan(agent, goal, perception)
                action_summary = self._act(agent, dt)
                response = self._respond(agent, perception, interpretation)
                self._update_memory(agent, perception, interpretation, action_summary, response)

                step_summaries.append(
                    {
                        "tick": self.world.tick,
                        "agent_id": agent_id,
                        "goal": vars(goal),
                        "action": vars(agent.current_action),
                        "response": response,
                    }
                )

        return {
            "status": "ok",
            "tick": self.world.tick,
            "time": round(self.world.time, 2),
            "steps": steps,
            "updates": step_summaries,
            "state": self.get_state(),
        }

    def grounded_chat(self, agent_id: str, message: str, auto_tick: bool = True) -> Dict[str, Any]:
        self.queue_user_chat(agent_id, message)
        if auto_tick:
            self.tick(dt=1.0, steps=1)

        agent = self.world.agents.get(agent_id)
        if agent is None:
            raise ValueError(f"Agent '{agent_id}' not found")

        return {
            "agent_id": agent_id,
            "message": message,
            "tick": self.world.tick,
            "time": round(self.world.time, 2),
            "response": agent.last_response,
            "active_goal": vars(agent.current_goal),
            "active_action": vars(agent.current_action),
            "emotion": vars(agent.emotional_state),
            "physical": vars(agent.physical_state),
            "perception": self._serialize_perception(agent.last_perception),
        }

    def get_state(self) -> Dict[str, Any]:
        world = self.world
        return {
            "time": round(world.time, 2),
            "tick": world.tick,
            "nearby_agents": world.nearby_agents,
            "objects": {
                obj_id: {
                    "id": obj.id,
                    "name": obj.name,
                    "kind": obj.kind,
                    "position": [round(obj.position[0], 2), round(obj.position[1], 2)],
                    "metadata": obj.metadata,
                }
                for obj_id, obj in world.objects.items()
            },
            "obstacles": [
                {
                    "id": obstacle.id,
                    "kind": obstacle.kind,
                    "position": [round(obstacle.position[0], 2), round(obstacle.position[1], 2)],
                    "radius": obstacle.radius,
                }
                for obstacle in world.obstacles
            ],
            "recent_events": [self._serialize_event(e) for e in world.recent_events[-25:]],
            "agents": {
                agent_id: self._serialize_agent(agent)
                for agent_id, agent in world.agents.items()
            },
        }

    def _perceive(self, agent: AgentState) -> PerceptionResult:
        visible_objects: List[Dict[str, Any]] = []
        for obj in self.world.objects.values():
            if self._is_visible(agent, obj.position):
                visible_objects.append(
                    {
                        "id": obj.id,
                        "name": obj.name,
                        "kind": obj.kind,
                        "position": [round(obj.position[0], 2), round(obj.position[1], 2)],
                        "distance": round(self._distance(agent.position, obj.position), 2),
                        "metadata": obj.metadata,
                    }
                )

        visible_agents: List[Dict[str, Any]] = []
        nearby_agents: List[Dict[str, Any]] = []
        for other in self.world.agents.values():
            if other.id == agent.id:
                continue
            d = self._distance(agent.position, other.position)
            if d <= 8.0:
                nearby_agents.append({"id": other.id, "name": other.name, "distance": round(d, 2)})
            if self._is_visible(agent, other.position):
                visible_agents.append(
                    {
                        "id": other.id,
                        "name": other.name,
                        "position": [round(other.position[0], 2), round(other.position[1], 2)],
                        "distance": round(d, 2),
                    }
                )

        recent_events = [
            self._serialize_event(event)
            for event in self.world.recent_events[-15:]
            if self._distance(agent.position, event.position) <= 9.0
        ]

        remembered = [
            {
                "id": memory.id,
                "tick": memory.tick,
                "category": memory.category,
                "content": memory.content,
                "confidence": memory.confidence,
            }
            for memory in agent.memory[-8:]
        ]

        perception = PerceptionResult(
            visible_objects=visible_objects,
            visible_agents=visible_agents,
            nearby_agents=nearby_agents,
            recent_events=recent_events,
            user_messages=list(agent.pending_user_messages),
            remembered=remembered,
        )
        agent.last_perception = perception
        return perception

    def _interpret(self, agent: AgentState, perception: PerceptionResult) -> Dict[str, Any]:
        user_intent: Optional[str] = None
        if perception.user_messages:
            text = perception.user_messages[-1].lower()
            if "where" in text or "location" in text:
                user_intent = "location"
            elif "help" in text:
                user_intent = "help"
            elif "status" in text:
                user_intent = "status"
            else:
                user_intent = "chat"

        threat_level = 0.0
        for event in perception.recent_events:
            if "blocked" in event["content"].lower() or "danger" in event["content"].lower():
                threat_level += 0.25
        threat_level = min(1.0, threat_level + agent.physical_state.stress * 0.2)

        needs: List[str] = []
        if agent.physical_state.energy < 0.4:
            needs.append("rest")
        if agent.physical_state.hunger > 0.65:
            needs.append("food")
        if threat_level > 0.5:
            needs.append("safety")

        interpretation = {
            "user_intent": user_intent,
            "threat_level": round(threat_level, 2),
            "needs": needs,
            "context_summary": f"objects={len(perception.visible_objects)}, nearby_agents={len(perception.nearby_agents)}, user_msgs={len(perception.user_messages)}",
        }
        agent.last_interpretation = interpretation
        return interpretation

    def _update_emotional_physical(
        self,
        agent: AgentState,
        perception: PerceptionResult,
        interpretation: Dict[str, Any],
        dt: float,
    ) -> None:
        e = agent.emotional_state
        p = agent.physical_state

        p.hunger = self._clamp(p.hunger + 0.012 * dt)
        p.energy = self._clamp(p.energy - 0.018 * dt)
        p.stamina = self._clamp(p.stamina - 0.010 * dt)

        e.engagement = self._clamp(e.engagement - 0.012 * dt)
        e.curiosity = self._clamp(e.curiosity - 0.008 * dt)
        e.anxiety = self._clamp(e.anxiety - 0.010 * dt)
        e.fatigue_feel = self._clamp(e.fatigue_feel + 0.015 * dt)

        external = self.behavior_adapter.evaluate(agent, perception, interpretation)

        for key, delta in external.get("emotion_delta", {}).items():
            if hasattr(e, key):
                setattr(e, key, self._clamp(getattr(e, key) + float(delta)))
        for key, delta in external.get("physical_delta", {}).items():
            if hasattr(p, key):
                setattr(p, key, self._clamp(getattr(p, key) + float(delta)))

        if interpretation.get("user_intent"):
            e.engagement = self._clamp(e.engagement + 0.08)
            e.calm = self._clamp(e.calm + 0.02)
        if interpretation.get("threat_level", 0) > 0.45:
            e.anxiety = self._clamp(e.anxiety + 0.09)
            p.stress = self._clamp(p.stress + 0.05)
        if agent.current_action.name == "rest" and agent.current_action.status == "in_progress":
            p.energy = self._clamp(p.energy + 0.05 * dt)
            p.stamina = self._clamp(p.stamina + 0.045 * dt)
            e.fatigue_feel = self._clamp(e.fatigue_feel - 0.05 * dt)

        e.fatigue_feel = self._clamp((1.0 - p.energy) * 0.7 + e.fatigue_feel * 0.3)

    def _select_goal(
        self,
        agent: AgentState,
        perception: PerceptionResult,
        interpretation: Dict[str, Any],
    ) -> GoalState:
        scores = {
            "respond_user": 0.0,
            "rest": 0.0,
            "eat": 0.0,
            "inspect": 0.0,
            "patrol": 0.1,
        }

        if perception.user_messages:
            scores["respond_user"] += 0.95
        scores["rest"] += max(0.0, 0.7 - agent.physical_state.energy)
        scores["eat"] += max(0.0, agent.physical_state.hunger - 0.55)
        scores["inspect"] += 0.25 if perception.visible_objects else 0.0
        scores["inspect"] += agent.emotional_state.curiosity * 0.2

        for goal_name, bias in self.behavior_adapter.evaluate(agent, perception, interpretation).get("goal_bias", {}).items():
            if goal_name in scores:
                scores[goal_name] += float(bias)

        goal_name = max(scores, key=scores.get)
        reason = f"scores={{{', '.join(f'{k}:{round(v, 2)}' for k, v in scores.items())}}}"

        readable_name = {
            "respond_user": "Respond to user",
            "rest": "Recover energy",
            "eat": "Find food",
            "inspect": "Inspect environment",
            "patrol": "Patrol area",
        }[goal_name]

        goal = GoalState(name=readable_name, priority=round(scores[goal_name], 2), reason=reason)
        agent.current_goal = goal
        return goal

    def _plan(self, agent: AgentState, goal: GoalState, perception: PerceptionResult) -> PlanState:
        steps: List[str]
        if goal.name == "Respond to user":
            steps = ["face_user", "speak"]
        elif goal.name == "Recover energy":
            steps = ["rest"]
        elif goal.name == "Find food":
            food_object = next((obj for obj in perception.visible_objects if obj.get("metadata", {}).get("food")), None)
            if food_object:
                steps = [f"move_to:{food_object['id']}", f"interact:{food_object['id']}"]
            else:
                steps = ["patrol"]
        elif goal.name == "Inspect environment" and perception.visible_objects:
            nearest = sorted(perception.visible_objects, key=lambda obj: obj["distance"])[0]
            steps = [f"move_to:{nearest['id']}", f"observe:{nearest['id']}"]
        else:
            steps = ["patrol"]

        if agent.current_plan.steps != steps or agent.current_plan.cursor >= len(agent.current_plan.steps):
            agent.current_plan = PlanState(steps=steps, cursor=0)
        return agent.current_plan

    def _act(self, agent: AgentState, dt: float) -> Dict[str, Any]:
        if agent.current_action.status != "in_progress":
            self._start_next_action(agent)

        action = agent.current_action
        action.elapsed += dt

        if action.name == "move_to" and action.target_position is not None:
            reached = self._move_toward(agent, action.target_position, dt)
            if reached:
                action.status = "completed"
        elif action.name == "rest":
            if action.elapsed >= action.duration:
                action.status = "completed"
        elif action.name in ("speak", "observe", "interact", "face_user", "patrol"):
            if action.elapsed >= action.duration:
                action.status = "completed"

        if action.status == "completed":
            self._record_event(
                event_type="action_complete",
                source_agent_id=agent.id,
                target_id=action.target_id,
                position=agent.position,
                content=f"{agent.name} completed action {action.name}",
            )
            agent.current_plan.cursor += 1
            action.status = "idle"
            action.name = "idle"
            action.elapsed = 0.0
            action.duration = 0.0
            action.target_id = None
            action.target_position = None

        return {
            "action": action.name,
            "status": action.status,
            "position": [round(agent.position[0], 2), round(agent.position[1], 2)],
        }

    def _start_next_action(self, agent: AgentState) -> None:
        if not agent.current_plan.steps or agent.current_plan.cursor >= len(agent.current_plan.steps):
            agent.current_action = ActionState()
            return

        step = agent.current_plan.steps[agent.current_plan.cursor]
        action = ActionState(status="in_progress")

        if step.startswith("move_to:"):
            obj_id = step.split(":", 1)[1]
            target = self.world.objects.get(obj_id)
            if target is None:
                agent.current_plan.cursor += 1
                return
            action.name = "move_to"
            action.target_id = obj_id
            action.target_position = target.position
            dist = self._distance(agent.position, target.position)
            action.duration = max(0.5, dist / max(0.1, agent.walk_speed))
        elif step.startswith("interact:"):
            action.name = "interact"
            action.target_id = step.split(":", 1)[1]
            action.duration = 1.0
        elif step.startswith("observe:"):
            action.name = "observe"
            action.target_id = step.split(":", 1)[1]
            action.duration = 0.9
        elif step == "face_user":
            action.name = "face_user"
            action.duration = 0.4
        elif step == "speak":
            action.name = "speak"
            action.duration = 0.8
            if agent.pending_user_messages:
                agent.pending_user_messages.clear()
        elif step == "rest":
            action.name = "rest"
            action.duration = 2.2
        else:
            action.name = "patrol"
            patrol_target = self._patrol_target(agent)
            action.target_position = patrol_target
            action.duration = 1.5

        agent.current_action = action

    def _respond(self, agent: AgentState, perception: PerceptionResult, interpretation: Dict[str, Any]) -> str:
        latest = perception.user_messages[-1] if perception.user_messages else ""
        goal = agent.current_goal.name
        action = agent.current_action.name
        p = agent.physical_state
        e = agent.emotional_state

        nearby = ", ".join(obj["name"] for obj in perception.visible_objects[:3]) or "nothing notable"
        pos_text = f"({agent.position[0]:.1f}, {agent.position[1]:.1f})"

        lower = latest.lower()
        if "where" in lower or "location" in lower:
            response = f"I am at {pos_text}. Nearby I can perceive {nearby}."
        elif "status" in lower:
            response = (
                f"Goal: {goal}. Action: {action}. Energy {p.energy:.2f}, stamina {p.stamina:.2f}, "
                f"hunger {p.hunger:.2f}, anxiety {e.anxiety:.2f}."
            )
        elif "help" in lower:
            response = f"I can help by sharing context: goal is '{goal}', currently '{action}', and I perceive {nearby}."
        elif latest:
            response = (
                f"Under current context ({interpretation['context_summary']}), I feel engagement {e.engagement:.2f} "
                f"and fatigue {e.fatigue_feel:.2f}. My focus is '{goal}' while doing '{action}'."
            )
        else:
            response = f"Monitoring world state at {pos_text}; goal '{goal}', action '{action}'."

        agent.last_response = response
        return response

    def _update_memory(
        self,
        agent: AgentState,
        perception: PerceptionResult,
        interpretation: Dict[str, Any],
        action_summary: Dict[str, Any],
        response: str,
    ) -> None:
        snippets = [
            f"perception: objects={len(perception.visible_objects)} agents={len(perception.visible_agents)}",
            f"interpretation: intent={interpretation.get('user_intent')} threat={interpretation.get('threat_level')}",
            f"action: {action_summary['action']} status={action_summary['status']}",
            f"response: {response}",
        ]

        for category, content in (
            ("perception", snippets[0]),
            ("interpretation", snippets[1]),
            ("action", snippets[2]),
            ("response", snippets[3]),
        ):
            memory = MemoryEvent(
                id=self._next_memory_id(),
                tick=self.world.tick,
                time=self.world.time,
                category=category,
                content=content,
                confidence=0.75,
                related_ids=[agent.id],
            )
            agent.memory.append(memory)

        if len(agent.memory) > 220:
            agent.memory = agent.memory[-220:]

    def _refresh_nearby_agents(self) -> None:
        mapping: Dict[str, List[str]] = {}
        for agent_id, agent in self.world.agents.items():
            seen: List[str] = []
            for other_id, other in self.world.agents.items():
                if agent_id == other_id:
                    continue
                if self._distance(agent.position, other.position) <= 8.0:
                    seen.append(other_id)
            mapping[agent_id] = seen
        self.world.nearby_agents = mapping

    def _move_toward(self, agent: AgentState, target: Vector2, dt: float) -> bool:
        dx = target[0] - agent.position[0]
        dy = target[1] - agent.position[1]
        dist = sqrt(dx * dx + dy * dy)
        if dist <= 0.05:
            agent.position = target
            return True

        direction = atan2(dy, dx)
        step = agent.walk_speed * dt
        if step >= dist:
            agent.position = target
            agent.facing_radians = direction
            return True

        agent.position = (
            agent.position[0] + cos(direction) * step,
            agent.position[1] + sin(direction) * step,
        )
        agent.facing_radians = direction
        return False

    def _patrol_target(self, agent: AgentState) -> Vector2:
        base_angle = (self.world.tick % 360) * (pi / 180.0)
        radius = 2.0
        return (
            agent.position[0] + cos(base_angle) * radius,
            agent.position[1] + sin(base_angle) * radius,
        )

    def _is_visible(self, agent: AgentState, target_position: Vector2) -> bool:
        if self._distance(agent.position, target_position) > agent.vision_range:
            return False
        direction = atan2(target_position[1] - agent.position[1], target_position[0] - agent.position[0])
        rel = self._normalize_angle(direction - agent.facing_radians)
        return abs(rel) <= agent.fov_radians / 2.0

    def _record_event(
        self,
        event_type: str,
        source_agent_id: Optional[str],
        target_id: Optional[str],
        position: Vector2,
        content: str,
    ) -> None:
        event = SimulationEvent(
            id=self._next_event_id(),
            tick=self.world.tick,
            time=self.world.time,
            event_type=event_type,
            source_agent_id=source_agent_id,
            target_id=target_id,
            position=(position[0], position[1]),
            content=content,
        )
        self.world.recent_events.append(event)
        if len(self.world.recent_events) > 300:
            self.world.recent_events = self.world.recent_events[-300:]

    def _serialize_agent(self, agent: AgentState) -> Dict[str, Any]:
        return {
            "id": agent.id,
            "name": agent.name,
            "position": [round(agent.position[0], 2), round(agent.position[1], 2)],
            "facing_radians": round(agent.facing_radians, 3),
            "emotion": vars(agent.emotional_state),
            "physical": vars(agent.physical_state),
            "current_goal": vars(agent.current_goal),
            "current_plan": {
                "steps": agent.current_plan.steps,
                "cursor": agent.current_plan.cursor,
            },
            "current_action": vars(agent.current_action),
            "last_response": agent.last_response,
            "last_interpretation": agent.last_interpretation,
            "last_perception": self._serialize_perception(agent.last_perception),
            "memory": [
                {
                    "id": m.id,
                    "tick": m.tick,
                    "time": round(m.time, 2),
                    "category": m.category,
                    "content": m.content,
                    "confidence": m.confidence,
                    "related_ids": m.related_ids,
                }
                for m in agent.memory[-20:]
            ],
        }

    def _serialize_perception(self, perception: Optional[PerceptionResult]) -> Dict[str, Any]:
        if perception is None:
            return {
                "visible_objects": [],
                "visible_agents": [],
                "nearby_agents": [],
                "recent_events": [],
                "user_messages": [],
                "remembered": [],
            }
        return {
            "visible_objects": perception.visible_objects,
            "visible_agents": perception.visible_agents,
            "nearby_agents": perception.nearby_agents,
            "recent_events": perception.recent_events,
            "user_messages": perception.user_messages,
            "remembered": perception.remembered,
        }

    def _serialize_event(self, event: SimulationEvent) -> Dict[str, Any]:
        return {
            "id": event.id,
            "tick": event.tick,
            "time": round(event.time, 2),
            "event_type": event.event_type,
            "source_agent_id": event.source_agent_id,
            "target_id": event.target_id,
            "position": [round(event.position[0], 2), round(event.position[1], 2)],
            "content": event.content,
        }

    @staticmethod
    def _distance(a: Vector2, b: Vector2) -> float:
        return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    @staticmethod
    def _normalize_angle(value: float) -> float:
        while value > pi:
            value -= 2 * pi
        while value < -pi:
            value += 2 * pi
        return value

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, value))

    def _next_event_id(self) -> str:
        self._event_counter += 1
        return f"evt-{self._event_counter}"

    def _next_memory_id(self) -> str:
        self._memory_counter += 1
        return f"mem-{self._memory_counter}"
