"""Simulation-centered backend engine.

Implements a multi-agent cognition loop:
perception -> interpretation -> emotional/physical update ->
goal selection -> plan/action selection -> execution -> memory update ->
response generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, cos, pi, sin, sqrt
from typing import Any, Dict, List, Optional, Tuple


# ===== Data model =====


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
    properties: Dict[str, Any] = field(default_factory=dict)


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
    related_ids: List[str] = field(default_factory=list)


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
    agent_id: str
    nearby_visible_objects: List[Dict[str, Any]]
    nearby_visible_agents: List[Dict[str, Any]]
    observed_events: List[Dict[str, Any]]
    user_chat_input: List[str]
    remembered_facts: List[Dict[str, Any]]


@dataclass
class Interpretation:
    salient_objects: List[Dict[str, Any]]
    social_signals: List[str]
    inferred_needs: List[str]
    threat_level: float
    user_intent: Optional[str]
    summary: str


@dataclass
class WorldState:
    time: float
    tick: int
    agents: Dict[str, AgentState]
    objects: Dict[str, WorldObject]
    obstacles: List[Obstacle]
    events: List[Event]


# ===== Pure/helper logic =====


def clamp(v: float, low: float, high: float) -> float:
    return max(low, min(high, v))


def distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def angle_to(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return atan2(b[1] - a[1], b[0] - a[0])


def normalize_angle(x: float) -> float:
    while x > pi:
        x -= 2 * pi
    while x < -pi:
        x += 2 * pi
    return x


def is_visible(agent: AgentState, target: Tuple[float, float]) -> bool:
    if distance(agent.position, target) > agent.vision_range:
        return False
    rel = normalize_angle(angle_to(agent.position, target) - agent.facing_radians)
    return abs(rel) <= (agent.field_of_view_radians / 2)


def emotion(agent: AgentState, key: str) -> float:
    d = agent.emotional_state.dimensions.get(key)
    return d.intensity if d else 0.0


def add_emotion(agent: AgentState, key: str, delta: float, decay: float = 0.04) -> None:
    d = agent.emotional_state.dimensions.get(key)
    if d is None:
        d = EmotionDimension(intensity=0.0, decay_per_tick=decay)
        agent.emotional_state.dimensions[key] = d
    d.intensity = clamp(d.intensity + delta, 0.0, 1.0)


def decay_emotions(agent: AgentState, dt: float) -> None:
    for d in agent.emotional_state.dimensions.values():
        d.intensity = clamp(d.intensity - d.decay_per_tick * dt, 0.0, 1.0)


def recent_memory(agent: AgentState, n: int = 6) -> List[Dict[str, Any]]:
    return [
        {
            "category": m.category,
            "content": m.content,
            "confidence": m.confidence,
            "related_ids": m.related_ids,
            "tick": m.tick,
        }
        for m in agent.memory[-n:]
    ]


def build_perception(world: WorldState, agent: AgentState) -> Perception:
    visible_objects = []
    for obj in world.objects.values():
        if is_visible(agent, obj.position):
            visible_objects.append(
                {
                    "id": obj.id,
                    "name": obj.name,
                    "kind": obj.kind,
                    "position": obj.position,
                    "distance": round(distance(agent.position, obj.position), 2),
                }
            )

    visible_agents = []
    for other in world.agents.values():
        if other.id != agent.id and is_visible(agent, other.position):
            visible_agents.append(
                {
                    "id": other.id,
                    "name": other.name,
                    "position": other.position,
                    "distance": round(distance(agent.position, other.position), 2),
                }
            )

    observed_events = [
        {
            "id": e.id,
            "event_type": e.event_type,
            "content": e.content,
            "tick": e.tick,
            "source_agent_id": e.source_agent_id,
        }
        for e in world.events[-20:]
        if distance(agent.position, e.position) <= agent.vision_range + 2.0
    ]

    return Perception(
        agent_id=agent.id,
        nearby_visible_objects=visible_objects,
        nearby_visible_agents=visible_agents,
        observed_events=observed_events,
        user_chat_input=list(agent.pending_user_chat),
        remembered_facts=recent_memory(agent),
    )


def interpret_perception(perception: Perception, agent: AgentState) -> Interpretation:
    salient = sorted(perception.nearby_visible_objects, key=lambda x: x.get("distance", 999))[:3]

    signals: List[str] = []
    if perception.user_chat_input:
        signals.append("user_engaged")
    if perception.nearby_visible_agents:
        signals.append("others_nearby")

    needs: List[str] = []
    if agent.physical_state.energy < 0.35:
        needs.append("rest")
    if agent.physical_state.hunger > 0.65:
        needs.append("find_food")

    threat = 0.0
    if any("blocked" in e["content"] for e in perception.observed_events):
        threat += 0.3
    threat += 0.25 * emotion(agent, "anxiety")
    threat = clamp(threat, 0.0, 1.0)

    user_intent: Optional[str] = None
    if perception.user_chat_input:
        msg = perception.user_chat_input[-1].lower()
        if "help" in msg:
            user_intent = "request_help"
        elif "where" in msg:
            user_intent = "request_location"
        elif "hello" in msg or "hi" in msg:
            user_intent = "greeting"
        else:
            user_intent = "general_chat"

    return Interpretation(
        salient_objects=salient,
        social_signals=signals,
        inferred_needs=needs,
        threat_level=threat,
        user_intent=user_intent,
        summary=f"Saw {len(perception.nearby_visible_objects)} objects and {len(perception.nearby_visible_agents)} agents.",
    )


def update_emotional_and_physical_state(agent: AgentState, interp: Interpretation, dt: float) -> None:
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
        add_emotion(agent, "irritation", 0.09)

    p.stress_load = clamp(
        p.stress_load + (emotion(agent, "anxiety") * 0.02) - (emotion(agent, "engagement") * 0.01),
        0.0,
        1.0,
    )


def score_goals(agent: AgentState, perception: Perception, interp: Interpretation) -> List[GoalState]:
    e = agent.physical_state.energy
    h = agent.physical_state.hunger
    anx = emotion(agent, "anxiety")
    eng = emotion(agent, "engagement")
    fat = emotion(agent, "fatigue")

    goals = [
        GoalState(
            name="respond_to_user",
            score=clamp(0.2 + (0.6 if perception.user_chat_input else 0.0) + eng * 0.2, 0.0, 1.0),
            urgency=0.8 if perception.user_chat_input else 0.3,
            reason="User message present" if perception.user_chat_input else "Maintain social presence",
        ),
        GoalState(
            name="rest",
            score=clamp((1.0 - e) * 0.55 + fat * 0.35 + anx * 0.1, 0.0, 1.0),
            urgency=clamp((1.0 - e) + fat * 0.4, 0.0, 1.0),
            reason="Low energy/fatigue",
        ),
        GoalState(
            name="inspect_nearby_object",
            score=clamp(0.2 + (0.35 if interp.salient_objects else 0.0) + (0.1 if h > 0.55 else 0.0), 0.0, 1.0),
            urgency=0.45,
            reason="Objects in view",
        ),
        GoalState(
            name="socialize_with_agent",
            score=clamp(0.15 + (0.35 if perception.nearby_visible_agents else 0.0) + eng * 0.2, 0.0, 1.0),
            urgency=0.5,
            reason="Nearby social opportunity",
        ),
        GoalState(
            name="explore",
            score=clamp(0.3 + (0.15 if not interp.salient_objects else 0.0), 0.0, 1.0),
            urgency=0.35,
            reason="Situational awareness",
        ),
    ]
    return sorted(goals, key=lambda g: g.score + g.urgency * 0.4, reverse=True)


def select_goal(agent: AgentState, goals: List[GoalState]) -> GoalState:
    chosen = goals[0]
    agent.goals = goals
    agent.current_goal = chosen
    return chosen


def select_plan_and_action(agent: AgentState, perception: Perception, interp: Interpretation) -> ActionState:
    if agent.current_action.status == "in_progress":
        return agent.current_action

    goal = agent.current_goal.name if agent.current_goal else "explore"

    if goal == "respond_to_user" and perception.user_chat_input:
        agent.current_plan = ["attend_user", "speak_grounded_reply"]
        return ActionState(kind="speak", status="in_progress", duration=1.0)

    if goal == "rest":
        spot = next((o for o in perception.nearby_visible_objects if o["kind"] in {"bench", "station"}), None)
        if spot and spot["distance"] > 1.1:
            agent.current_plan = ["move_to_rest_spot", "rest"]
            return ActionState(kind="walk", status="in_progress", target_id=spot["id"], target_position=tuple(spot["position"]))
        if spot:
            agent.current_plan = ["rest"]
            return ActionState(kind="rest", status="in_progress", target_id=spot["id"], duration=2.0)

    if goal == "inspect_nearby_object" and interp.salient_objects:
        target = interp.salient_objects[0]
        if target["distance"] > 1.4:
            agent.current_plan = ["walk_to_object", "orient", "interact"]
            return ActionState(kind="walk", status="in_progress", target_id=target["id"], target_position=tuple(target["position"]))
        agent.current_plan = ["orient", "interact"]
        return ActionState(kind="orient", status="in_progress", target_position=tuple(target["position"]), duration=1.0)

    if goal == "socialize_with_agent" and perception.nearby_visible_agents:
        t = perception.nearby_visible_agents[0]
        if t["distance"] > 1.5:
            agent.current_plan = ["approach_agent", "greet"]
            return ActionState(kind="walk", status="in_progress", target_id=t["id"], target_position=tuple(t["position"]))
        agent.current_plan = ["greet"]
        return ActionState(kind="speak", status="in_progress", target_id=t["id"], duration=1.0)

    waypoint = (
        agent.position[0] + cos(agent.facing_radians) * 2.0,
        agent.position[1] + sin(agent.facing_radians) * 2.0,
    )
    agent.current_plan = ["explore_forward"]
    return ActionState(kind="walk", status="in_progress", target_position=waypoint)


def execute_action(world: WorldState, agent: AgentState, dt: float) -> List[Event]:
    events: List[Event] = []
    a = agent.current_action

    if a.kind == "walk" and a.target_position:
        speed = 1.1 * (0.5 + agent.physical_state.stamina * 0.8)
        desired = angle_to(agent.position, a.target_position)
        diff = normalize_angle(desired - agent.facing_radians)
        turn = clamp(diff, -1.0 * dt, 1.0 * dt)
        agent.facing_radians = normalize_angle(agent.facing_radians + turn)

        step = speed * dt
        d = distance(agent.position, a.target_position)
        if d <= step:
            agent.position = a.target_position
            a.status = "completed"
        else:
            agent.position = (
                agent.position[0] + cos(agent.facing_radians) * step,
                agent.position[1] + sin(agent.facing_radians) * step,
            )
            a.status = "in_progress"

    elif a.kind == "orient" and a.target_position:
        desired = angle_to(agent.position, a.target_position)
        diff = normalize_angle(desired - agent.facing_radians)
        turn = clamp(diff, -1.2 * dt, 1.2 * dt)
        agent.facing_radians = normalize_angle(agent.facing_radians + turn)
        if abs(diff) < 0.12:
            a.status = "completed"

    elif a.kind in {"interact", "speak", "rest"}:
        a.elapsed += dt
        if a.elapsed >= max(0.5, a.duration):
            a.status = "completed"

    if a.status == "completed":
        events.append(
            Event(
                id=f"evt-{world.tick}-{agent.id}-{len(world.events)}",
                timestamp=world.time,
                tick=world.tick,
                event_type="action_completed",
                source_agent_id=agent.id,
                target_id=a.target_id,
                content=f"{agent.name} completed {a.kind}",
                position=agent.position,
            )
        )
        agent.action_history.append({"tick": world.tick, "action": a.kind, "target_id": a.target_id})
        agent.current_action = ActionState()

    return events


def update_memory(world: WorldState, agent: AgentState, perception: Perception, interp: Interpretation) -> None:
    for obs in perception.observed_events[-3:]:
        agent.memory.append(
            MemoryItem(
                timestamp=world.time,
                tick=world.tick,
                category="observation",
                content=obs["content"],
                confidence=0.7,
                related_ids=[x for x in [obs.get("source_agent_id")] if x],
            )
        )

    for msg in perception.user_chat_input[-2:]:
        agent.memory.append(
            MemoryItem(
                timestamp=world.time,
                tick=world.tick,
                category="user_chat",
                content=msg,
                confidence=0.95,
            )
        )

    agent.memory.append(
        MemoryItem(
            timestamp=world.time,
            tick=world.tick,
            category="interpretation",
            content=interp.summary,
            confidence=0.6,
        )
    )

    if len(agent.memory) > 200:
        agent.memory = agent.memory[-200:]


def social_tone(agent: AgentState) -> str:
    if emotion(agent, "fatigue") > 0.65:
        return "tired but cooperative"
    if emotion(agent, "anxiety") > 0.6:
        return "cautious"
    if emotion(agent, "engagement") > 0.55:
        return "warm"
    return "neutral"


def generate_grounded_response(agent: AgentState, perception: Perception) -> str:
    tone = social_tone(agent)
    goal = agent.current_goal.name if agent.current_goal else "explore"
    visible = ", ".join(o["name"] for o in perception.nearby_visible_objects[:2]) or "nothing notable nearby"
    mem = perception.remembered_facts[-1]["content"] if perception.remembered_facts else "no strong memory"

    if perception.user_chat_input:
        msg = perception.user_chat_input[-1]
        return (
            f"({tone}) You said '{msg}'. I can currently see {visible}. "
            f"Energy={agent.physical_state.energy:.2f}, stress={agent.physical_state.stress_load:.2f}. "
            f"Goal={goal}, action={agent.current_action.kind}. Memory hint: {mem}."
        )

    return (
        f"({tone}) Observing {visible}. Goal={goal}, action={agent.current_action.kind}, "
        f"energy={agent.physical_state.energy:.2f}."
    )


# ===== Engine =====


class SimulationEngine:
    def __init__(self) -> None:
        self.world = self._init_world()

    def _init_world(self) -> WorldState:
        rico = AgentState(id="agent-1", name="Rico", position=(0.0, 0.0), facing_radians=0.0)
        rico.emotional_state.dimensions = {
            "engagement": EmotionDimension(0.4, 0.03),
            "anxiety": EmotionDimension(0.1, 0.05),
            "fatigue": EmotionDimension(0.2, 0.02),
            "irritation": EmotionDimension(0.05, 0.06),
        }

        nova = AgentState(id="agent-2", name="Nova", position=(4.0, 1.5), facing_radians=pi)
        nova.emotional_state.dimensions = {
            "engagement": EmotionDimension(0.3, 0.03),
            "anxiety": EmotionDimension(0.1, 0.05),
            "fatigue": EmotionDimension(0.1, 0.02),
        }

        objects = {
            "obj-1": WorldObject(id="obj-1", name="Info Kiosk", kind="kiosk", position=(3.0, 0.0)),
            "obj-2": WorldObject(id="obj-2", name="Charging Bench", kind="bench", position=(-2.0, -1.0)),
            "obj-3": WorldObject(id="obj-3", name="Snack Station", kind="station", position=(1.0, 3.0)),
        }

        return WorldState(
            time=0.0,
            tick=0,
            agents={rico.id: rico, nova.id: nova},
            objects=objects,
            obstacles=[Obstacle(id="obs-1", kind="pillar", position=(1.5, 1.2), radius=0.4)],
            events=[],
        )

    def queue_user_chat(self, agent_id: str, message: str) -> None:
        agent = self.world.agents.get(agent_id)
        if agent is None:
            raise ValueError(f"Unknown agent_id '{agent_id}'")
        agent.pending_user_chat.append(message)

    def tick(self, dt: float = 1.0, steps: int = 1) -> Dict[str, Any]:
        dt = clamp(dt, 0.1, 5.0)
        steps = max(1, min(50, steps))

        all_responses: List[Dict[str, str]] = []
        events_added: List[Event] = []

        for _ in range(steps):
            self.world.tick += 1
            self.world.time += dt

            for agent in self.world.agents.values():
                # 1) perception
                p = build_perception(self.world, agent)
                # 2) interpretation
                i = interpret_perception(p, agent)
                # 3) emotional/physical update
                update_emotional_and_physical_state(agent, i, dt)
                # 4) goal selection
                select_goal(agent, score_goals(agent, p, i))
                # 5) plan/action selection
                agent.current_action = select_plan_and_action(agent, p, i)
                # 6) execute
                events_added.extend(execute_action(self.world, agent, dt))
                # 7) memory
                update_memory(self.world, agent, p, i)
                # 8) response
                agent.last_response = generate_grounded_response(agent, p)
                all_responses.append({"agent_id": agent.id, "response": agent.last_response})
                agent.pending_user_chat = []

            self.world.events.extend(events_added)
            if len(self.world.events) > 500:
                self.world.events = self.world.events[-500:]

        return {
            "time": self.world.time,
            "tick": self.world.tick,
            "responses": all_responses,
            "events_added": [self._event_dict(e) for e in events_added],
            "state": self.get_state(),
        }

    def grounded_chat(self, agent_id: str, message: str, auto_tick: bool = True) -> Dict[str, Any]:
        self.queue_user_chat(agent_id, message)
        if auto_tick:
            self.tick(dt=1.0, steps=1)
            agent = self.world.agents[agent_id]
            return {
                "agent_id": agent_id,
                "message": message,
                "response": agent.last_response,
                "goal": agent.current_goal.name if agent.current_goal else "explore",
                "action": agent.current_action.kind,
                "tick": self.world.tick,
                "time": self.world.time,
            }
        return {
            "agent_id": agent_id,
            "message": message,
            "response": "Queued message. Advance tick for grounded response.",
            "tick": self.world.tick,
            "time": self.world.time,
        }

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
        return {
            "id": e.id,
            "timestamp": e.timestamp,
            "tick": e.tick,
            "event_type": e.event_type,
            "source_agent_id": e.source_agent_id,
            "target_id": e.target_id,
            "content": e.content,
            "position": list(e.position),
        }

    @staticmethod
    def _object_dict(o: WorldObject) -> Dict[str, Any]:
        return {
            "id": o.id,
            "name": o.name,
            "kind": o.kind,
            "position": list(o.position),
            "interactable": o.interactable,
            "properties": o.properties,
        }

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
            "physical_state": {
                "energy": a.physical_state.energy,
                "stamina": a.physical_state.stamina,
                "hunger": a.physical_state.hunger,
                "stress_load": a.physical_state.stress_load,
            },
            "emotional_state": {
                k: {"intensity": v.intensity, "decay_per_tick": v.decay_per_tick}
                for k, v in a.emotional_state.dimensions.items()
            },
            "goals": [{"name": g.name, "score": g.score, "urgency": g.urgency, "reason": g.reason} for g in a.goals],
            "current_goal": {
                "name": a.current_goal.name,
                "score": a.current_goal.score,
                "urgency": a.current_goal.urgency,
                "reason": a.current_goal.reason,
            }
            if a.current_goal
            else None,
            "current_plan": a.current_plan,
            "current_action": {
                "kind": a.current_action.kind,
                "status": a.current_action.status,
                "target_id": a.current_action.target_id,
                "target_position": list(a.current_action.target_position) if a.current_action.target_position else None,
                "elapsed": a.current_action.elapsed,
                "duration": a.current_action.duration,
            },
            "action_history": a.action_history[-20:],
            "memory": [
                {
                    "timestamp": m.timestamp,
                    "tick": m.tick,
                    "category": m.category,
                    "content": m.content,
                    "confidence": m.confidence,
                    "related_ids": m.related_ids,
                }
                for m in a.memory[-30:]
            ],
            "relationships": {rid: {"trust": r.trust, "familiarity": r.familiarity, "affinity": r.affinity} for rid, r in a.relationships.items()},
            "last_response": a.last_response,
        }
