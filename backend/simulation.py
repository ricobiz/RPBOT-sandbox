"""Simulation-centered backend engine.

Multi-agent data model and deterministic cognition loop:
perception -> interpretation -> emotional/physical update -> goal selection ->
plan/action selection -> execution -> memory update -> response generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, cos, pi, sin, sqrt
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Event:
    id: str
    timestamp: float
    tick: int
    event_type: str
    source_agent_id: Optional[str]
    target_id: Optional[str]
    content: str
    position: Tuple[float, float]


@dataclass
class WorldObject:
    id: str
    name: str
    kind: str
    position: Tuple[float, float]
    interactable: bool = True


@dataclass
class Obstacle:
    id: str
    kind: str
    position: Tuple[float, float]
    radius: float


@dataclass
class MemoryItem:
    timestamp: float
    tick: int
    category: str
    content: str
    confidence: float


@dataclass
class EmotionDimension:
    intensity: float
    decay_per_tick: float


@dataclass
class EmotionalState:
    dimensions: Dict[str, EmotionDimension] = field(default_factory=dict)


@dataclass
class PhysicalState:
    energy: float = 0.8
    stamina: float = 0.8
    hunger: float = 0.2
    stress_load: float = 0.2


@dataclass
class RelationshipState:
    trust: float = 0.5
    familiarity: float = 0.2
    affinity: float = 0.5


@dataclass
class GoalState:
    name: str
    score: float
    urgency: float
    reason: str


@dataclass
class ActionState:
    kind: str = "idle"
    status: str = "idle"
    target_id: Optional[str] = None
    target_position: Optional[Tuple[float, float]] = None
    elapsed: float = 0.0
    duration: float = 0.0


@dataclass
class AgentState:
    id: str
    name: str
    position: Tuple[float, float]
    facing_radians: float
    vision_range: float = 6.0
    field_of_view_radians: float = pi * 0.9
    memory: List[MemoryItem] = field(default_factory=list)
    action_history: List[Dict[str, Any]] = field(default_factory=list)
    relationships: Dict[str, RelationshipState] = field(default_factory=dict)
    emotional_state: EmotionalState = field(default_factory=EmotionalState)
    physical_state: PhysicalState = field(default_factory=PhysicalState)
    goals: List[GoalState] = field(default_factory=list)
    current_goal: Optional[GoalState] = None
    current_plan: List[str] = field(default_factory=list)
    current_action: ActionState = field(default_factory=ActionState)
    pending_user_chat: List[str] = field(default_factory=list)
    last_response: str = ""


@dataclass
class Perception:
    nearby_visible_objects: List[Dict[str, Any]]
    nearby_visible_agents: List[Dict[str, Any]]
    observed_events: List[Dict[str, Any]]
    user_chat_input: List[str]
    remembered_facts: List[Dict[str, Any]]


@dataclass
class Interpretation:
    threat_level: float
    user_intent: Optional[str]
    salient_objects: List[Dict[str, Any]]
    summary: str


@dataclass
class WorldState:
    time: float
    tick: int
    agents: Dict[str, AgentState]
    objects: Dict[str, WorldObject]
    obstacles: List[Obstacle]
    events: List[Event]


def clamp(v: float, low: float, high: float) -> float:
    return max(low, min(high, v))


def distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def angle_to(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return atan2(b[1] - a[1], b[0] - a[0])


def normalize_angle(v: float) -> float:
    while v > pi:
        v -= 2 * pi
    while v < -pi:
        v += 2 * pi
    return v


def emotion(agent: AgentState, key: str) -> float:
    d = agent.emotional_state.dimensions.get(key)
    return d.intensity if d else 0.0


def add_emotion(agent: AgentState, key: str, delta: float, decay: float = 0.04) -> None:
    d = agent.emotional_state.dimensions.get(key)
    if d is None:
        d = EmotionDimension(0.0, decay)
        agent.emotional_state.dimensions[key] = d
    d.intensity = clamp(d.intensity + delta, 0.0, 1.0)


def decay_emotions(agent: AgentState, dt: float) -> None:
    for d in agent.emotional_state.dimensions.values():
        d.intensity = clamp(d.intensity - d.decay_per_tick * dt, 0.0, 1.0)


def is_visible(agent: AgentState, pos: Tuple[float, float]) -> bool:
    if distance(agent.position, pos) > agent.vision_range:
        return False
    rel = normalize_angle(angle_to(agent.position, pos) - agent.facing_radians)
    return abs(rel) <= (agent.field_of_view_radians / 2)


def build_perception(world: WorldState, agent: AgentState) -> Perception:
    visible_objects = [
        {
            "id": o.id,
            "name": o.name,
            "kind": o.kind,
            "position": o.position,
            "distance": round(distance(agent.position, o.position), 2),
        }
        for o in world.objects.values()
        if is_visible(agent, o.position)
    ]
    visible_agents = [
        {
            "id": a.id,
            "name": a.name,
            "position": a.position,
            "distance": round(distance(agent.position, a.position), 2),
        }
        for a in world.agents.values()
        if a.id != agent.id and is_visible(agent, a.position)
    ]
    observed_events = [
        {"id": e.id, "event_type": e.event_type, "content": e.content, "tick": e.tick}
        for e in world.events[-20:]
        if distance(agent.position, e.position) <= agent.vision_range + 2.0
    ]
    remembered = [
        {"category": m.category, "content": m.content, "confidence": m.confidence, "tick": m.tick}
        for m in agent.memory[-6:]
    ]
    return Perception(visible_objects, visible_agents, observed_events, list(agent.pending_user_chat), remembered)


def interpret_perception(perception: Perception, agent: AgentState) -> Interpretation:
    msg = perception.user_chat_input[-1].lower() if perception.user_chat_input else ""
    user_intent = None
    if msg:
        if "help" in msg:
            user_intent = "request_help"
        elif "where" in msg:
            user_intent = "request_location"
        elif "hi" in msg or "hello" in msg:
            user_intent = "greeting"
        else:
            user_intent = "general_chat"
    threat = clamp((0.25 if any("blocked" in e["content"] for e in perception.observed_events) else 0.0) + emotion(agent, "anxiety") * 0.3, 0.0, 1.0)
    salient = sorted(perception.nearby_visible_objects, key=lambda x: x["distance"])[:3]
    return Interpretation(threat, user_intent, salient, f"visible_objects={len(perception.nearby_visible_objects)}")


def update_emotional_and_physical(agent: AgentState, interp: Interpretation, dt: float) -> None:
    decay_emotions(agent, dt)
    p = agent.physical_state
    p.hunger = clamp(p.hunger + 0.01 * dt, 0.0, 1.0)
    p.energy = clamp(p.energy - 0.015 * dt, 0.0, 1.0)
    p.stamina = clamp(p.stamina - 0.01 * dt, 0.0, 1.0)
    if agent.current_action.kind == "rest":
        p.energy = clamp(p.energy + 0.035 * dt, 0.0, 1.0)
        p.stamina = clamp(p.stamina + 0.03 * dt, 0.0, 1.0)
    if interp.user_intent:
        add_emotion(agent, "engagement", 0.12)
    if interp.threat_level > 0.4:
        add_emotion(agent, "anxiety", 0.10)
    if p.energy < 0.3:
        add_emotion(agent, "fatigue", 0.14)
    if p.hunger > 0.7:
        add_emotion(agent, "irritation", 0.08)
    p.stress_load = clamp(p.stress_load + emotion(agent, "anxiety") * 0.02 - emotion(agent, "engagement") * 0.01, 0.0, 1.0)


def score_goals(agent: AgentState, p: Perception, i: Interpretation) -> List[GoalState]:
    goals = [
        GoalState("respond_to_user", clamp(0.2 + (0.6 if p.user_chat_input else 0.0) + emotion(agent, "engagement") * 0.2, 0.0, 1.0), 0.8 if p.user_chat_input else 0.3, "user chat"),
        GoalState("rest", clamp((1.0 - agent.physical_state.energy) * 0.6 + emotion(agent, "fatigue") * 0.3, 0.0, 1.0), clamp((1.0 - agent.physical_state.energy), 0.0, 1.0), "energy recovery"),
        GoalState("inspect", clamp(0.2 + (0.35 if i.salient_objects else 0.0), 0.0, 1.0), 0.45, "inspect nearby"),
        GoalState("socialize", clamp(0.15 + (0.35 if p.nearby_visible_agents else 0.0), 0.0, 1.0), 0.5, "social behavior"),
        GoalState("explore", 0.3, 0.35, "ambient exploration"),
    ]
    return sorted(goals, key=lambda g: g.score + 0.4 * g.urgency, reverse=True)


def select_plan_and_action(agent: AgentState, p: Perception, i: Interpretation) -> ActionState:
    if agent.current_action.status == "in_progress":
        return agent.current_action
    goal = agent.current_goal.name if agent.current_goal else "explore"
    if goal == "respond_to_user" and p.user_chat_input:
        agent.current_plan = ["attend_user", "speak"]
        return ActionState(kind="speak", status="in_progress", duration=1.0)
    if goal == "rest":
        rest_spot = next((o for o in p.nearby_visible_objects if o["kind"] in {"bench", "station"}), None)
        if rest_spot and rest_spot["distance"] > 1.1:
            agent.current_plan = ["walk_to_rest", "rest"]
            return ActionState(kind="walk", status="in_progress", target_id=rest_spot["id"], target_position=tuple(rest_spot["position"]))
        if rest_spot:
            agent.current_plan = ["rest"]
            return ActionState(kind="rest", status="in_progress", target_id=rest_spot["id"], duration=2.0)
    if goal == "inspect" and i.salient_objects:
        target = i.salient_objects[0]
        if target["distance"] > 1.4:
            agent.current_plan = ["walk_to_object", "orient", "interact"]
            return ActionState(kind="walk", status="in_progress", target_id=target["id"], target_position=tuple(target["position"]))
        agent.current_plan = ["orient", "interact"]
        return ActionState(kind="orient", status="in_progress", target_position=tuple(target["position"]), duration=1.0)
    if goal == "socialize" and p.nearby_visible_agents:
        t = p.nearby_visible_agents[0]
        if t["distance"] > 1.5:
            agent.current_plan = ["approach", "greet"]
            return ActionState(kind="walk", status="in_progress", target_id=t["id"], target_position=tuple(t["position"]))
        return ActionState(kind="speak", status="in_progress", target_id=t["id"], duration=1.0)
    waypoint = (agent.position[0] + cos(agent.facing_radians) * 2.0, agent.position[1] + sin(agent.facing_radians) * 2.0)
    agent.current_plan = ["explore_forward"]
    return ActionState(kind="walk", status="in_progress", target_position=waypoint)


def execute_action(world: WorldState, agent: AgentState, dt: float) -> List[Event]:
    out: List[Event] = []
    a = agent.current_action
    if a.kind == "walk" and a.target_position:
        desired = angle_to(agent.position, a.target_position)
        diff = normalize_angle(desired - agent.facing_radians)
        agent.facing_radians = normalize_angle(agent.facing_radians + clamp(diff, -1.0 * dt, 1.0 * dt))
        step = 1.1 * (0.5 + agent.physical_state.stamina * 0.8) * dt
        d = distance(agent.position, a.target_position)
        if d <= step:
            agent.position = a.target_position
            a.status = "completed"
        else:
            agent.position = (agent.position[0] + cos(agent.facing_radians) * step, agent.position[1] + sin(agent.facing_radians) * step)
    elif a.kind == "orient" and a.target_position:
        desired = angle_to(agent.position, a.target_position)
        diff = normalize_angle(desired - agent.facing_radians)
        agent.facing_radians = normalize_angle(agent.facing_radians + clamp(diff, -1.2 * dt, 1.2 * dt))
        if abs(diff) < 0.12:
            a.status = "completed"
    elif a.kind in {"rest", "speak", "interact"}:
        a.elapsed += dt
        if a.elapsed >= max(0.5, a.duration):
            a.status = "completed"

    if a.status == "completed":
        out.append(Event(f"evt-{world.tick}-{agent.id}-{len(world.events)}", world.time, world.tick, "action_completed", agent.id, a.target_id, f"{agent.name} completed {a.kind}", agent.position))
        agent.action_history.append({"tick": world.tick, "action": a.kind, "target_id": a.target_id})
        agent.current_action = ActionState()
    return out


def update_memory(world: WorldState, agent: AgentState, p: Perception, i: Interpretation) -> None:
    for e in p.observed_events[-2:]:
        agent.memory.append(MemoryItem(world.time, world.tick, "observation", e["content"], 0.7))
    for msg in p.user_chat_input[-2:]:
        agent.memory.append(MemoryItem(world.time, world.tick, "user_chat", msg, 0.95))
    agent.memory.append(MemoryItem(world.time, world.tick, "interpretation", i.summary, 0.6))
    if len(agent.memory) > 200:
        agent.memory = agent.memory[-200:]


def grounded_response(agent: AgentState, p: Perception) -> str:
    tone = "warm" if emotion(agent, "engagement") > 0.55 else "cautious" if emotion(agent, "anxiety") > 0.6 else "neutral"
    goal = agent.current_goal.name if agent.current_goal else "explore"
    action = agent.current_action.kind
    visible = ", ".join([o["name"] for o in p.nearby_visible_objects[:2]]) or "nothing notable nearby"
    last_memory = p.remembered_facts[-1]["content"] if p.remembered_facts else "none"
    if p.user_chat_input:
        return f"({tone}) You said '{p.user_chat_input[-1]}'. I currently see {visible}. Energy={agent.physical_state.energy:.2f}, stress={agent.physical_state.stress_load:.2f}, goal={goal}, action={action}, memory={last_memory}."
    return f"({tone}) I observe {visible}. goal={goal}, action={action}."


class SimulationEngine:
    def __init__(self) -> None:
        self.world = self._init_world()

    def _init_world(self) -> WorldState:
        rico = AgentState("agent-1", "Rico", (0.0, 0.0), 0.0)
        rico.emotional_state.dimensions = {
            "engagement": EmotionDimension(0.4, 0.03),
            "anxiety": EmotionDimension(0.1, 0.05),
            "fatigue": EmotionDimension(0.2, 0.02),
            "irritation": EmotionDimension(0.05, 0.06),
        }
        nova = AgentState("agent-2", "Nova", (4.0, 1.5), pi)
        nova.emotional_state.dimensions = {
            "engagement": EmotionDimension(0.3, 0.03),
            "anxiety": EmotionDimension(0.1, 0.05),
            "fatigue": EmotionDimension(0.1, 0.02),
        }
        objects = {
            "obj-1": WorldObject("obj-1", "Info Kiosk", "kiosk", (3.0, 0.0)),
            "obj-2": WorldObject("obj-2", "Charging Bench", "bench", (-2.0, -1.0)),
            "obj-3": WorldObject("obj-3", "Snack Station", "station", (1.0, 3.0)),
        }
        return WorldState(0.0, 0, {rico.id: rico, nova.id: nova}, objects, [Obstacle("obs-1", "pillar", (1.5, 1.2), 0.4)], [])

    def queue_user_chat(self, agent_id: str, message: str) -> None:
        agent = self.world.agents.get(agent_id)
        if not agent:
            raise ValueError(f"Unknown agent_id '{agent_id}'")
        agent.pending_user_chat.append(message)

    def tick(self, dt: float = 1.0, steps: int = 1) -> Dict[str, Any]:
        dt = clamp(dt, 0.1, 5.0)
        steps = max(1, min(steps, 50))
        responses: List[Dict[str, str]] = []
        events_added: List[Event] = []

        for _ in range(steps):
            self.world.tick += 1
            self.world.time += dt
            step_events: List[Event] = []
            for agent in self.world.agents.values():
                # 1) perception
                p = build_perception(self.world, agent)
                # 2) interpretation
                i = interpret_perception(p, agent)
                # 3) emotional/physical update
                update_emotional_and_physical(agent, i, dt)
                # 4) goal scoring/selection
                goals = score_goals(agent, p, i)
                agent.goals = goals
                agent.current_goal = goals[0]
                # 5) plan/action selection
                agent.current_action = select_plan_and_action(agent, p, i)
                # 6) action execution with space/time progression
                step_events.extend(execute_action(self.world, agent, dt))
                # 7) memory update
                update_memory(self.world, agent, p, i)
                # 8) grounded response generation
                agent.last_response = grounded_response(agent, p)
                responses.append({"agent_id": agent.id, "response": agent.last_response})
                agent.pending_user_chat = []
            self.world.events.extend(step_events)
            events_added.extend(step_events)
            if len(self.world.events) > 500:
                self.world.events = self.world.events[-500:]

        return {
            "time": self.world.time,
            "tick": self.world.tick,
            "responses": responses,
            "events_added": [self._event_dict(e) for e in events_added],
            "state": self.get_state(),
        }

    def grounded_chat(self, agent_id: str, message: str, auto_tick: bool = True) -> Dict[str, Any]:
        self.queue_user_chat(agent_id, message)
        if auto_tick:
            result = self.tick(1.0, 1)
            agent = self.world.agents[agent_id]
            return {
                "agent_id": agent_id,
                "message": message,
                "response": agent.last_response,
                "goal": agent.current_goal.name if agent.current_goal else "explore",
                "action": agent.current_action.kind,
                "tick": self.world.tick,
                "time": self.world.time,
                "tick_result": result,
            }
        return {"agent_id": agent_id, "message": message, "status": "queued", "tick": self.world.tick, "time": self.world.time}

    def get_state(self) -> Dict[str, Any]:
        return {
            "time": self.world.time,
            "tick": self.world.tick,
            "agents": {k: self._agent_dict(v) for k, v in self.world.agents.items()},
            "objects": {k: self._object_dict(v) for k, v in self.world.objects.items()},
            "obstacles": [self._obstacle_dict(o) for o in self.world.obstacles],
            "events": [self._event_dict(e) for e in self.world.events[-100:]],
        }

    @staticmethod
    def _event_dict(e: Event) -> Dict[str, Any]:
        return {"id": e.id, "timestamp": e.timestamp, "tick": e.tick, "event_type": e.event_type, "source_agent_id": e.source_agent_id, "target_id": e.target_id, "content": e.content, "position": list(e.position)}

    @staticmethod
    def _object_dict(o: WorldObject) -> Dict[str, Any]:
        return {"id": o.id, "name": o.name, "kind": o.kind, "position": list(o.position), "interactable": o.interactable}

    @staticmethod
    def _obstacle_dict(o: Obstacle) -> Dict[str, Any]:
        return {"id": o.id, "kind": o.kind, "position": list(o.position), "radius": o.radius}

    @staticmethod
    def _agent_dict(a: AgentState) -> Dict[str, Any]:
        return {
            "id": a.id,
            "name": a.name,
            "position": list(a.position),
            "facing_radians": a.facing_radians,
            "physical_state": {"energy": a.physical_state.energy, "stamina": a.physical_state.stamina, "hunger": a.physical_state.hunger, "stress_load": a.physical_state.stress_load},
            "emotional_state": {k: {"intensity": v.intensity, "decay_per_tick": v.decay_per_tick} for k, v in a.emotional_state.dimensions.items()},
            "goals": [{"name": g.name, "score": g.score, "urgency": g.urgency, "reason": g.reason} for g in a.goals],
            "current_goal": ({"name": a.current_goal.name, "score": a.current_goal.score, "urgency": a.current_goal.urgency, "reason": a.current_goal.reason} if a.current_goal else None),
            "current_plan": a.current_plan,
            "current_action": {"kind": a.current_action.kind, "status": a.current_action.status, "target_id": a.current_action.target_id, "target_position": list(a.current_action.target_position) if a.current_action.target_position else None, "elapsed": a.current_action.elapsed, "duration": a.current_action.duration},
            "action_history": a.action_history[-20:],
            "memory": [{"timestamp": m.timestamp, "tick": m.tick, "category": m.category, "content": m.content, "confidence": m.confidence} for m in a.memory[-30:]],
            "relationships": {rid: {"trust": r.trust, "familiarity": r.familiarity, "affinity": r.affinity} for rid, r in a.relationships.items()},
            "last_response": a.last_response,
        }
