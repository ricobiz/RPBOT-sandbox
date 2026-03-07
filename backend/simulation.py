"""Simulation-centered backend engine.

Implements explicit world/agent data structures and a deterministic cognition
pipeline:

perception -> interpretation -> emotional/physical update -> goal scoring/
selection -> plan/action selection -> execution -> memory update -> grounded
response generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, cos, pi, sin, sqrt
from typing import Any, Dict, List, Optional, Tuple


# ==============================
# Data structures
# ==============================


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
    kind: str = "idle"  # idle | walk | orient | interact | speak | rest
    status: str = "idle"  # idle | in_progress | completed
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
    fov_radians: float = pi * 0.9
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


# ==============================
# Helper / pure logic
# ==============================


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def angle_to(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return atan2(b[1] - a[1], b[0] - a[0])


def normalize_angle(value: float) -> float:
    while value > pi:
        value -= 2 * pi
    while value < -pi:
        value += 2 * pi
    return value


def emotion_value(agent: AgentState, key: str) -> float:
    dimension = agent.emotional_state.dimensions.get(key)
    return dimension.intensity if dimension else 0.0


def add_emotion(agent: AgentState, key: str, delta: float, decay: float = 0.04) -> None:
    dimension = agent.emotional_state.dimensions.get(key)
    if dimension is None:
        dimension = EmotionDimension(intensity=0.0, decay_per_tick=decay)
        agent.emotional_state.dimensions[key] = dimension
    dimension.intensity = clamp(dimension.intensity + delta, 0.0, 1.0)


def decay_emotions(agent: AgentState, dt: float) -> None:
    for dimension in agent.emotional_state.dimensions.values():
        dimension.intensity = clamp(dimension.intensity - dimension.decay_per_tick * dt, 0.0, 1.0)


def is_visible(agent: AgentState, target_position: Tuple[float, float]) -> bool:
    if distance(agent.position, target_position) > agent.vision_range:
        return False
    relative_angle = normalize_angle(angle_to(agent.position, target_position) - agent.facing_radians)
    return abs(relative_angle) <= (agent.fov_radians / 2)


def _remembered_facts(agent: AgentState, limit: int = 6) -> List[Dict[str, Any]]:
    return [
        {
            "category": m.category,
            "content": m.content,
            "confidence": m.confidence,
            "related_ids": m.related_ids,
            "tick": m.tick,
        }
        for m in agent.memory[-limit:]
    ]


def build_perception(world: WorldState, agent: AgentState) -> Perception:
    """Only exposes what the agent can perceive locally + memory + user input."""
    objects = [
        {
            "id": obj.id,
            "name": obj.name,
            "kind": obj.kind,
            "position": obj.position,
            "distance": round(distance(agent.position, obj.position), 2),
        }
        for obj in world.objects.values()
        if is_visible(agent, obj.position)
    ]

    agents = [
        {
            "id": other.id,
            "name": other.name,
            "position": other.position,
            "distance": round(distance(agent.position, other.position), 2),
        }
        for other in world.agents.values()
        if other.id != agent.id and is_visible(agent, other.position)
    ]

    events = [
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
        nearby_visible_objects=objects,
        nearby_visible_agents=agents,
        observed_events=events,
        user_chat_input=list(agent.pending_user_chat),
        remembered_facts=_remembered_facts(agent),
    )


def interpret_perception(perception: Perception, agent: AgentState) -> Interpretation:
    salient_objects = sorted(
        perception.nearby_visible_objects,
        key=lambda item: item.get("distance", 999),
    )[:3]

    social_signals: List[str] = []
    if perception.user_chat_input:
        social_signals.append("user_engaged")
    if perception.nearby_visible_agents:
        social_signals.append("others_nearby")

    inferred_needs: List[str] = []
    if agent.physical_state.energy < 0.35:
        inferred_needs.append("rest")
    if agent.physical_state.hunger > 0.65:
        inferred_needs.append("food")
    if emotion_value(agent, "anxiety") > 0.6:
        inferred_needs.append("safety")

    threat_level = 0.0
    if any("blocked" in e["content"] for e in perception.observed_events):
        threat_level += 0.3
    threat_level += emotion_value(agent, "anxiety") * 0.25
    threat_level = clamp(threat_level, 0.0, 1.0)

    user_intent: Optional[str] = None
    if perception.user_chat_input:
        latest = perception.user_chat_input[-1].lower()
        if "help" in latest:
            user_intent = "request_help"
        elif "where" in latest:
            user_intent = "request_location"
        elif "hi" in latest or "hello" in latest:
            user_intent = "greeting"
        else:
            user_intent = "general_chat"

    return Interpretation(
        salient_objects=salient_objects,
        social_signals=social_signals,
        inferred_needs=inferred_needs,
        threat_level=threat_level,
        user_intent=user_intent,
        summary=(
            f"objects={len(perception.nearby_visible_objects)} "
            f"agents={len(perception.nearby_visible_agents)} "
            f"user_msgs={len(perception.user_chat_input)}"
        ),
    )


def update_emotional_and_physical(agent: AgentState, interpretation: Interpretation, dt: float) -> None:
    """Emotion system with intensity + decay + physical factors."""
    decay_emotions(agent, dt)

    p = agent.physical_state
    p.hunger = clamp(p.hunger + 0.01 * dt, 0.0, 1.0)
    p.energy = clamp(p.energy - 0.015 * dt, 0.0, 1.0)
    p.stamina = clamp(p.stamina - 0.01 * dt, 0.0, 1.0)

    if agent.current_action.kind == "rest":
        p.energy = clamp(p.energy + 0.035 * dt, 0.0, 1.0)
        p.stamina = clamp(p.stamina + 0.03 * dt, 0.0, 1.0)

    if interpretation.user_intent is not None:
        add_emotion(agent, "engagement", 0.12)
    if interpretation.threat_level > 0.4:
        add_emotion(agent, "anxiety", 0.10)
    if p.energy < 0.3:
        add_emotion(agent, "fatigue", 0.14)
    if p.hunger > 0.7:
        add_emotion(agent, "irritation", 0.08)

    p.stress_load = clamp(
        p.stress_load + emotion_value(agent, "anxiety") * 0.02 - emotion_value(agent, "engagement") * 0.01,
        0.0,
        1.0,
    )


def score_goals(agent: AgentState, perception: Perception, interpretation: Interpretation) -> List[GoalState]:
    energy = agent.physical_state.energy
    engagement = emotion_value(agent, "engagement")
    anxiety = emotion_value(agent, "anxiety")
    fatigue = emotion_value(agent, "fatigue")

    goals = [
        GoalState(
            name="respond_to_user",
            score=clamp(0.2 + (0.6 if perception.user_chat_input else 0.0) + engagement * 0.2, 0.0, 1.0),
            urgency=0.8 if perception.user_chat_input else 0.3,
            reason="User chat pending" if perception.user_chat_input else "Maintain social presence",
        ),
        GoalState(
            name="rest",
            score=clamp((1.0 - energy) * 0.55 + fatigue * 0.35 + anxiety * 0.1, 0.0, 1.0),
            urgency=clamp((1.0 - energy) + fatigue * 0.4, 0.0, 1.0),
            reason="Recover energy",
        ),
        GoalState(
            name="inspect_nearby_object",
            score=clamp(0.2 + (0.35 if interpretation.salient_objects else 0.0), 0.0, 1.0),
            urgency=0.45,
            reason="Interesting nearby object",
        ),
        GoalState(
            name="socialize_with_agent",
            score=clamp(0.15 + (0.35 if perception.nearby_visible_agents else 0.0) + engagement * 0.2, 0.0, 1.0),
            urgency=0.5,
            reason="Nearby social opportunity",
        ),
        GoalState(
            name="explore",
            score=0.3,
            urgency=0.35,
            reason="Maintain world awareness",
        ),
    ]
    return sorted(goals, key=lambda g: g.score + 0.4 * g.urgency, reverse=True)


def select_plan_and_action(agent: AgentState, perception: Perception, interpretation: Interpretation) -> ActionState:
    if agent.current_action.status == "in_progress":
        return agent.current_action

    goal = agent.current_goal.name if agent.current_goal else "explore"

    if goal == "respond_to_user" and perception.user_chat_input:
        agent.current_plan = ["attend_user", "speak"]
        return ActionState(kind="speak", status="in_progress", duration=1.0)

    if goal == "rest":
        rest_spot = next((o for o in perception.nearby_visible_objects if o["kind"] in {"bench", "station"}), None)
        if rest_spot and rest_spot["distance"] > 1.1:
            agent.current_plan = ["walk_to_rest", "rest"]
            return ActionState(
                kind="walk",
                status="in_progress",
                target_id=rest_spot["id"],
                target_position=tuple(rest_spot["position"]),
            )
        if rest_spot:
            agent.current_plan = ["rest"]
            return ActionState(kind="rest", status="in_progress", target_id=rest_spot["id"], duration=2.0)

    if goal == "inspect_nearby_object" and interpretation.salient_objects:
        target = interpretation.salient_objects[0]
        if target["distance"] > 1.4:
            agent.current_plan = ["walk_to_object", "orient", "interact"]
            return ActionState(
                kind="walk",
                status="in_progress",
                target_id=target["id"],
                target_position=tuple(target["position"]),
            )
        agent.current_plan = ["orient", "interact"]
        return ActionState(kind="orient", status="in_progress", target_position=tuple(target["position"]), duration=1.0)

    if goal == "socialize_with_agent" and perception.nearby_visible_agents:
        target_agent = perception.nearby_visible_agents[0]
        if target_agent["distance"] > 1.5:
            agent.current_plan = ["approach_agent", "greet"]
            return ActionState(
                kind="walk",
                status="in_progress",
                target_id=target_agent["id"],
                target_position=tuple(target_agent["position"]),
            )
        agent.current_plan = ["greet"]
        return ActionState(kind="speak", status="in_progress", target_id=target_agent["id"], duration=1.0)

    waypoint = (
        agent.position[0] + cos(agent.facing_radians) * 2.0,
        agent.position[1] + sin(agent.facing_radians) * 2.0,
    )
    agent.current_plan = ["explore_forward"]
    return ActionState(kind="walk", status="in_progress", target_position=waypoint)


def execute_action(world: WorldState, agent: AgentState, dt: float) -> List[Event]:
    """Actions progress over ticks (walk/orient/interact)."""
    emitted: List[Event] = []
    action = agent.current_action

    if action.kind == "walk" and action.target_position:
        desired_heading = angle_to(agent.position, action.target_position)
        heading_diff = normalize_angle(desired_heading - agent.facing_radians)
        max_turn = 1.0 * dt
        agent.facing_radians = normalize_angle(agent.facing_radians + clamp(heading_diff, -max_turn, max_turn))

        speed = 1.1 * (0.5 + agent.physical_state.stamina * 0.8)
        step = speed * dt
        remaining = distance(agent.position, action.target_position)

        if remaining <= step:
            agent.position = action.target_position
            action.status = "completed"
        else:
            agent.position = (
                agent.position[0] + cos(agent.facing_radians) * step,
                agent.position[1] + sin(agent.facing_radians) * step,
            )
            action.status = "in_progress"

    elif action.kind == "orient" and action.target_position:
        desired_heading = angle_to(agent.position, action.target_position)
        heading_diff = normalize_angle(desired_heading - agent.facing_radians)
        max_turn = 1.2 * dt
        agent.facing_radians = normalize_angle(agent.facing_radians + clamp(heading_diff, -max_turn, max_turn))
        if abs(heading_diff) < 0.12:
            action.status = "completed"

    elif action.kind in {"rest", "interact", "speak"}:
        action.elapsed += dt
        if action.elapsed >= max(0.5, action.duration):
            action.status = "completed"

    if action.status == "completed":
        emitted.append(
            Event(
                id=f"evt-{world.tick}-{agent.id}-{len(world.events)}",
                timestamp=world.time,
                tick=world.tick,
                event_type="action_completed",
                source_agent_id=agent.id,
                target_id=action.target_id,
                content=f"{agent.name} completed {action.kind}",
                position=agent.position,
            )
        )
        agent.action_history.append(
            {
                "tick": world.tick,
                "action": action.kind,
                "target_id": action.target_id,
                "target_position": action.target_position,
            }
        )
        agent.current_action = ActionState()

    return emitted


def update_memory(world: WorldState, agent: AgentState, perception: Perception, interpretation: Interpretation) -> None:
    for observed in perception.observed_events[-2:]:
        agent.memory.append(
            MemoryItem(
                timestamp=world.time,
                tick=world.tick,
                category="observation",
                content=observed["content"],
                confidence=0.7,
                related_ids=[x for x in [observed.get("source_agent_id")] if x],
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
            content=interpretation.summary,
            confidence=0.6,
        )
    )

    if len(agent.memory) > 200:
        agent.memory = agent.memory[-200:]


def social_tone(agent: AgentState) -> str:
    fatigue = emotion_value(agent, "fatigue")
    anxiety = emotion_value(agent, "anxiety")
    engagement = emotion_value(agent, "engagement")

    if fatigue > 0.65:
        return "tired but cooperative"
    if anxiety > 0.6:
        return "cautious"
    if engagement > 0.55:
        return "warm"
    return "neutral"


def generate_grounded_response(agent: AgentState, perception: Perception) -> str:
    tone = social_tone(agent)
    goal = agent.current_goal.name if agent.current_goal else "explore"
    action = agent.current_action.kind
    visible = ", ".join(o["name"] for o in perception.nearby_visible_objects[:2]) or "nothing notable nearby"
    remembered = perception.remembered_facts[-1]["content"] if perception.remembered_facts else "no strong memory"

    if perception.user_chat_input:
        return (
            f"({tone}) You said '{perception.user_chat_input[-1]}'. I can see {visible}. "
            f"Energy={agent.physical_state.energy:.2f}, stress={agent.physical_state.stress_load:.2f}. "
            f"Goal={goal}, action={action}. Memory hint: {remembered}."
        )

    return f"({tone}) I observe {visible}. Goal={goal}, action={action}."


# ==============================
# Engine
# ==============================


class SimulationEngine:
    def __init__(self) -> None:
        self.world = self._create_world()

    def _create_world(self) -> WorldState:
        # Demo starts with one primary agent but model is multi-agent first-class.
        rico = AgentState(id="agent-1", name="Rico", position=(0.0, 0.0), facing_radians=0.0)
        rico.emotional_state.dimensions = {
            "engagement": EmotionDimension(0.4, 0.03),
            "anxiety": EmotionDimension(0.1, 0.05),
            "fatigue": EmotionDimension(0.2, 0.02),
            "irritation": EmotionDimension(0.05, 0.06),
        }

        # Additional agent to keep multi-agent behavior explicit.
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
        steps = max(1, min(steps, 50))

        all_responses: List[Dict[str, str]] = []
        all_events_added: List[Event] = []

        for _ in range(steps):
            self.world.tick += 1
            self.world.time += dt

            step_events: List[Event] = []

            for agent in self.world.agents.values():
                # 1) perception
                perception = build_perception(self.world, agent)

                # 2) interpretation
                interpretation = interpret_perception(perception, agent)

                # 3) emotional/physical update
                update_emotional_and_physical(agent, interpretation, dt)

                # 4) goal scoring and selection
                agent.goals = score_goals(agent, perception, interpretation)
                agent.current_goal = agent.goals[0]

                # 5) plan/action selection
                agent.current_action = select_plan_and_action(agent, perception, interpretation)

                # 6) action execution with spatial/time progression
                step_events.extend(execute_action(self.world, agent, dt))

                # 7) memory update
                update_memory(self.world, agent, perception, interpretation)

                # 8) grounded response generation
                agent.last_response = generate_grounded_response(agent, perception)
                all_responses.append({"agent_id": agent.id, "response": agent.last_response})

                # consume chat after processing this tick
                agent.pending_user_chat = []

            self.world.events.extend(step_events)
            all_events_added.extend(step_events)

            if len(self.world.events) > 500:
                self.world.events = self.world.events[-500:]

        return {
            "time": self.world.time,
            "tick": self.world.tick,
            "responses": all_responses,
            "events_added": [self._event_dict(e) for e in all_events_added],
            "state": self.get_state(),
        }

    def grounded_chat(self, agent_id: str, message: str, auto_tick: bool = True) -> Dict[str, Any]:
        self.queue_user_chat(agent_id, message)
        if auto_tick:
            tick_result = self.tick(dt=1.0, steps=1)
            agent = self.world.agents[agent_id]
            return {
                "agent_id": agent_id,
                "message": message,
                "response": agent.last_response,
                "goal": agent.current_goal.name if agent.current_goal else "explore",
                "action": agent.current_action.kind,
                "tick": self.world.tick,
                "time": self.world.time,
                "tick_result": tick_result,
            }

        return {
            "agent_id": agent_id,
            "message": message,
            "status": "queued",
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
    def _event_dict(event: Event) -> Dict[str, Any]:
        return {
            "id": event.id,
            "timestamp": event.timestamp,
            "tick": event.tick,
            "event_type": event.event_type,
            "source_agent_id": event.source_agent_id,
            "target_id": event.target_id,
            "content": event.content,
            "position": list(event.position),
        }

    @staticmethod
    def _object_dict(obj: WorldObject) -> Dict[str, Any]:
        return {
            "id": obj.id,
            "name": obj.name,
            "kind": obj.kind,
            "position": list(obj.position),
            "interactable": obj.interactable,
            "properties": obj.properties,
        }

    @staticmethod
    def _obstacle_dict(obstacle: Obstacle) -> Dict[str, Any]:
        return {
            "id": obstacle.id,
            "kind": obstacle.kind,
            "position": list(obstacle.position),
            "radius": obstacle.radius,
        }

    @staticmethod
    def _agent_dict(agent: AgentState) -> Dict[str, Any]:
        return {
            "id": agent.id,
            "name": agent.name,
            "position": list(agent.position),
            "facing_radians": agent.facing_radians,
            "physical_state": {
                "energy": agent.physical_state.energy,
                "stamina": agent.physical_state.stamina,
                "hunger": agent.physical_state.hunger,
                "stress_load": agent.physical_state.stress_load,
            },
            "emotional_state": {
                key: {"intensity": dim.intensity, "decay_per_tick": dim.decay_per_tick}
                for key, dim in agent.emotional_state.dimensions.items()
            },
            "goals": [
                {"name": g.name, "score": g.score, "urgency": g.urgency, "reason": g.reason}
                for g in agent.goals
            ],
            "current_goal": (
                {
                    "name": agent.current_goal.name,
                    "score": agent.current_goal.score,
                    "urgency": agent.current_goal.urgency,
                    "reason": agent.current_goal.reason,
                }
                if agent.current_goal
                else None
            ),
            "current_plan": agent.current_plan,
            "current_action": {
                "kind": agent.current_action.kind,
                "status": agent.current_action.status,
                "target_id": agent.current_action.target_id,
                "target_position": list(agent.current_action.target_position) if agent.current_action.target_position else None,
                "elapsed": agent.current_action.elapsed,
                "duration": agent.current_action.duration,
            },
            "action_history": agent.action_history[-20:],
            "memory": [
                {
                    "timestamp": m.timestamp,
                    "tick": m.tick,
                    "category": m.category,
                    "content": m.content,
                    "confidence": m.confidence,
                    "related_ids": m.related_ids,
                }
                for m in agent.memory[-30:]
            ],
            "relationships": {
                rid: {
                    "trust": rel.trust,
                    "familiarity": rel.familiarity,
                    "affinity": rel.affinity,
                }
                for rid, rel in agent.relationships.items()
            },
            "last_response": agent.last_response,
        }
