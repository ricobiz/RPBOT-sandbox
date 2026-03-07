"""Simulation-centered backend engine for RPBOT.

This module keeps simulation logic intentionally explicit and structured around
an agent cognition loop:

perception -> interpretation -> emotional/physical update ->
goal selection -> plan/action selection -> execution -> memory update ->
response generation

The design is multi-agent first (world.agents is a map), even though the demo
initializer only creates one primary agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, cos, pi, sin, sqrt
from typing import Any, Dict, List, Optional, Tuple


# -----------------------------
# Data structures
# -----------------------------


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
class EmotionalDimension:
    intensity: float
    decay_per_tick: float


@dataclass
class EmotionalState:
    dimensions: Dict[str, EmotionalDimension] = field(default_factory=dict)


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
    status: str = "idle"  # idle | in_progress | completed
    target_id: Optional[str] = None
    target_position: Optional[Tuple[float, float]] = None
    elapsed: float = 0.0
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


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


# -----------------------------
# Helper/pure functions
# -----------------------------


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def angle_to(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return atan2(b[1] - a[1], b[0] - a[0])


def normalize_angle(angle: float) -> float:
    while angle > pi:
        angle -= 2 * pi
    while angle < -pi:
        angle += 2 * pi
    return angle


def is_visible(
    agent_pos: Tuple[float, float],
    agent_facing: float,
    fov: float,
    max_range: float,
    target_pos: Tuple[float, float],
) -> bool:
    d = distance(agent_pos, target_pos)
    if d > max_range:
        return False
    direction = angle_to(agent_pos, target_pos)
    rel = normalize_angle(direction - agent_facing)
    return abs(rel) <= (fov / 2)


def emotion_value(agent: AgentState, key: str) -> float:
    dim = agent.emotional_state.dimensions.get(key)
    return dim.intensity if dim else 0.0


def add_emotion(agent: AgentState, key: str, delta: float, decay: float = 0.04) -> None:
    dim = agent.emotional_state.dimensions.get(key)
    if dim is None:
        dim = EmotionalDimension(intensity=0.0, decay_per_tick=decay)
        agent.emotional_state.dimensions[key] = dim
    dim.intensity = clamp(dim.intensity + delta, 0.0, 1.0)


def decay_emotions(agent: AgentState, dt: float) -> None:
    for dim in agent.emotional_state.dimensions.values():
        dim.intensity = clamp(dim.intensity - (dim.decay_per_tick * dt), 0.0, 1.0)


def remembered_facts(agent: AgentState, limit: int = 6) -> List[Dict[str, Any]]:
    recent = agent.memory[-limit:]
    return [
        {
            "category": m.category,
            "content": m.content,
            "confidence": m.confidence,
            "related_ids": m.related_ids,
            "tick": m.tick,
        }
        for m in recent
    ]


def build_perception(world: WorldState, agent: AgentState) -> Perception:
    visible_objects: List[Dict[str, Any]] = []
    visible_agents: List[Dict[str, Any]] = []

    for obj in world.objects.values():
        if is_visible(
            agent.position,
            agent.facing_radians,
            agent.field_of_view_radians,
            agent.vision_range,
            obj.position,
        ):
            visible_objects.append(
                {
                    "id": obj.id,
                    "name": obj.name,
                    "kind": obj.kind,
                    "position": obj.position,
                    "distance": round(distance(agent.position, obj.position), 2),
                }
            )

    for other in world.agents.values():
        if other.id == agent.id:
            continue
        if is_visible(
            agent.position,
            agent.facing_radians,
            agent.field_of_view_radians,
            agent.vision_range,
            other.position,
        ):
            visible_agents.append(
                {
                    "id": other.id,
                    "name": other.name,
                    "position": other.position,
                    "distance": round(distance(agent.position, other.position), 2),
                }
            )

    recent_events = [
        e
        for e in world.events[-20:]
        if distance(agent.position, e.position) <= agent.vision_range + 2.0
    ]
    observed_events = [
        {
            "id": e.id,
            "event_type": e.event_type,
            "content": e.content,
            "tick": e.tick,
            "source_agent_id": e.source_agent_id,
        }
        for e in recent_events
    ]

    perception = Perception(
        agent_id=agent.id,
        nearby_visible_objects=visible_objects,
        nearby_visible_agents=visible_agents,
        observed_events=observed_events,
        user_chat_input=list(agent.pending_user_chat),
        remembered_facts=remembered_facts(agent),
    )
    return perception


def interpret_perception(perception: Perception, agent: AgentState) -> Interpretation:
    salient_objects = sorted(
        perception.nearby_visible_objects,
        key=lambda o: o.get("distance", 999),
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
        inferred_needs.append("find_food")
    if emotion_value(agent, "anxiety") > 0.6:
        inferred_needs.append("safety")

    threat_level = 0.0
    threat_level += 0.3 if any("blocked" in e["content"] for e in perception.observed_events) else 0.0
    threat_level += 0.25 * emotion_value(agent, "anxiety")
    threat_level = clamp(threat_level, 0.0, 1.0)

    user_intent: Optional[str] = None
    if perception.user_chat_input:
        lower = perception.user_chat_input[-1].lower()
        if "help" in lower:
            user_intent = "request_help"
        elif "where" in lower:
            user_intent = "request_location"
        elif "hi" in lower or "hello" in lower:
            user_intent = "greeting"
        else:
            user_intent = "general_chat"

    summary = (
        f"Saw {len(perception.nearby_visible_objects)} objects, "
        f"{len(perception.nearby_visible_agents)} agents, "
        f"{len(perception.user_chat_input)} user messages."
    )

    return Interpretation(
        salient_objects=salient_objects,
        social_signals=social_signals,
        inferred_needs=inferred_needs,
        threat_level=threat_level,
        user_intent=user_intent,
        summary=summary,
    )


def update_emotional_and_physical_state(
    agent: AgentState,
    interpretation: Interpretation,
    dt: float,
) -> None:
    # Baseline decay
    decay_emotions(agent, dt)

    # Physical progression
    p = agent.physical_state
    p.hunger = clamp(p.hunger + 0.01 * dt, 0.0, 1.0)
    p.energy = clamp(p.energy - 0.015 * dt, 0.0, 1.0)
    p.stamina = clamp(p.stamina - 0.01 * dt, 0.0, 1.0)

    if agent.current_action.kind == "rest":
        p.energy = clamp(p.energy + 0.035 * dt, 0.0, 1.0)
        p.stamina = clamp(p.stamina + 0.03 * dt, 0.0, 1.0)
    if agent.current_action.kind == "walk":
        p.stress_load = clamp(p.stress_load + 0.01 * dt, 0.0, 1.0)

    # Emotion updates influenced by interpretation + physical factors
    if interpretation.user_intent in {"greeting", "general_chat", "request_help", "request_location"}:
        add_emotion(agent, "engagement", 0.12)
    if interpretation.threat_level > 0.4:
        add_emotion(agent, "anxiety", 0.10)
    if p.energy < 0.3:
        add_emotion(agent, "fatigue", 0.14)
    if p.hunger > 0.7:
        add_emotion(agent, "irritation", 0.09)

    # Physical state modifies social tone
    p.stress_load = clamp(
        p.stress_load + (emotion_value(agent, "anxiety") * 0.02) - (emotion_value(agent, "engagement") * 0.01),
        0.0,
        1.0,
    )


def score_goals(agent: AgentState, perception: Perception, interpretation: Interpretation) -> List[GoalState]:
    energy = agent.physical_state.energy
    hunger = agent.physical_state.hunger
    anxiety = emotion_value(agent, "anxiety")
    engagement = emotion_value(agent, "engagement")
    fatigue = emotion_value(agent, "fatigue")

    goals: List[GoalState] = []

    respond_score = 0.2 + (0.6 if perception.user_chat_input else 0.0) + engagement * 0.2
    goals.append(
        GoalState(
            name="respond_to_user",
            score=clamp(respond_score, 0.0, 1.0),
            urgency=0.8 if perception.user_chat_input else 0.3,
            reason="User message present" if perception.user_chat_input else "Keep social presence",
        )
    )

    rest_score = (1.0 - energy) * 0.55 + fatigue * 0.35 + anxiety * 0.1
    goals.append(
        GoalState(
            name="rest",
            score=clamp(rest_score, 0.0, 1.0),
            urgency=clamp((1.0 - energy) + fatigue * 0.4, 0.0, 1.0),
            reason="Low energy/fatigue" if rest_score > 0.45 else "Maintain readiness",
        )
    )

    inspect_score = 0.2 + (0.35 if interpretation.salient_objects else 0.0) + (0.1 if hunger > 0.55 else 0.0)
    goals.append(
        GoalState(
            name="inspect_nearby_object",
            score=clamp(inspect_score, 0.0, 1.0),
            urgency=0.45,
            reason="Objects in view" if interpretation.salient_objects else "Ambient exploration",
        )
    )

    socialize_score = 0.15 + (0.35 if perception.nearby_visible_agents else 0.0) + engagement * 0.2
    goals.append(
        GoalState(
            name="socialize_with_agent",
            score=clamp(socialize_score, 0.0, 1.0),
            urgency=0.5,
            reason="Nearby agent and engagement",
        )
    )

    explore_score = 0.3 + (0.15 if not interpretation.salient_objects else 0.0)
    goals.append(
        GoalState(
            name="explore",
            score=clamp(explore_score, 0.0, 1.0),
            urgency=0.35,
            reason="Maintain situational awareness",
        )
    )

    ranked = sorted(goals, key=lambda g: (g.score + g.urgency * 0.4), reverse=True)
    return ranked


def select_goal(agent: AgentState, scored_goals: List[GoalState]) -> GoalState:
    chosen = scored_goals[0]
    agent.goals = scored_goals
    agent.current_goal = chosen
    return chosen


def select_plan_and_action(
    agent: AgentState,
    perception: Perception,
    interpretation: Interpretation,
) -> ActionState:
    # If an action is still in progress, continue it.
    if agent.current_action.status == "in_progress":
        return agent.current_action

    goal_name = agent.current_goal.name if agent.current_goal else "explore"

    if goal_name == "respond_to_user" and perception.user_chat_input:
        agent.current_plan = ["attend_user", "speak_grounded_reply"]
        return ActionState(kind="speak", status="in_progress", duration=1.0)

    if goal_name == "rest":
        rest_spot = next((o for o in perception.nearby_visible_objects if o["kind"] in {"bench", "station"}), None)
        if rest_spot:
            if rest_spot["distance"] > 1.1:
                agent.current_plan = ["move_to_rest_spot", "rest"]
                return ActionState(
                    kind="walk",
                    status="in_progress",
                    target_id=rest_spot["id"],
                    target_position=tuple(rest_spot["position"]),
                )
            agent.current_plan = ["rest"]
            return ActionState(kind="rest", status="in_progress", duration=2.0, target_id=rest_spot["id"])

    if goal_name == "inspect_nearby_object" and interpretation.salient_objects:
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

    if goal_name == "socialize_with_agent" and perception.nearby_visible_agents:
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
        return ActionState(kind="speak", status="in_progress", duration=1.0, target_id=target_agent["id"])

    # Default exploration waypoint in front of current facing
    waypoint = (
        agent.position[0] + cos(agent.facing_radians) * 2.0,
        agent.position[1] + sin(agent.facing_radians) * 2.0,
    )
    agent.current_plan = ["explore_forward"]
    return ActionState(kind="walk", status="in_progress", target_position=waypoint)


def execute_action(world: WorldState, agent: AgentState, dt: float) -> List[Event]:
    events: List[Event] = []
    action = agent.current_action

    if action.kind == "idle":
        return events

    if action.kind == "walk" and action.target_position:
        speed = 1.1 * (0.5 + agent.physical_state.stamina * 0.8)
        target = action.target_position
        desired_heading = angle_to(agent.position, target)

        # Turning takes time; only partial turn each tick.
        turn_speed = 1.0 * dt
        heading_diff = normalize_angle(desired_heading - agent.facing_radians)
        heading_step = clamp(heading_diff, -turn_speed, turn_speed)
        agent.facing_radians = normalize_angle(agent.facing_radians + heading_step)

        step = speed * dt
        d = distance(agent.position, target)
        if d <= step:
            agent.position = target
            action.status = "completed"
        else:
            agent.position = (
                agent.position[0] + cos(agent.facing_radians) * step,
                agent.position[1] + sin(agent.facing_radians) * step,
            )
            action.status = "in_progress"

    elif action.kind == "orient" and action.target_position:
        desired_heading = angle_to(agent.position, action.target_position)
        turn_speed = 1.2 * dt
        heading_diff = normalize_angle(desired_heading - agent.facing_radians)
        heading_step = clamp(heading_diff, -turn_speed, turn_speed)
        agent.facing_radians = normalize_angle(agent.facing_radians + heading_step)
        if abs(heading_diff) < 0.12:
            action.status = "completed"

    elif action.kind in {"interact", "speak", "rest"}:
        action.elapsed += dt
        if action.elapsed >= max(0.5, action.duration):
            action.status = "completed"

    if action.status == "completed":
        events.append(
            Event(
                id=f"evt-{world.tick}-{agent.id}-{len(world.events) + len(events)}",
                timestamp=world.time,
                tick=world.tick,
                event_type="action_completed",
                source_agent_id=agent.id,
                target_id=action.target_id,
                content=f"{agent.name} completed action {action.kind}",
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
        agent.current_action = ActionState(kind="idle", status="idle")

    return events


def update_memory(
    world: WorldState,
    agent: AgentState,
    perception: Perception,
    interpretation: Interpretation,
) -> None:
    # Keep perceived events
    for obs in perception.observed_events[-3:]:
        agent.memory.append(
            MemoryItem(
                timestamp=world.time,
                tick=world.tick,
                category="observation",
                content=obs["content"],
                confidence=0.7,
                related_ids=[i for i in [obs.get("source_agent_id")] if i],
            )
        )

    # Keep user messages as high-confidence social memory
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

    # Keep interpretation summary
    agent.memory.append(
        MemoryItem(
            timestamp=world.time,
            tick=world.tick,
            category="interpretation",
            content=interpretation.summary,
            confidence=0.6,
        )
    )

    # Prune memory window
    if len(agent.memory) > 200:
        agent.memory = agent.memory[-200:]


def social_tone(agent: AgentState) -> str:
    anxiety = emotion_value(agent, "anxiety")
    engagement = emotion_value(agent, "engagement")
    fatigue = emotion_value(agent, "fatigue")

    if fatigue > 0.65:
        return "tired but cooperative"
    if anxiety > 0.6:
        return "cautious"
    if engagement > 0.55:
        return "warm"
    return "neutral"


def generate_grounded_response(
    agent: AgentState,
    perception: Perception,
    interpretation: Interpretation,
) -> str:
    tone = social_tone(agent)
    phys = agent.physical_state
    goal_name = agent.current_goal.name if agent.current_goal else "explore"
    action_name = agent.current_action.kind

    visible_obj_names = [o["name"] for o in perception.nearby_visible_objects[:2]]
    visible_text = ", ".join(visible_obj_names) if visible_obj_names else "nothing notable nearby"

    memory_hint = perception.remembered_facts[-1]["content"] if perception.remembered_facts else "no strong memory"

    if perception.user_chat_input:
        user_msg = perception.user_chat_input[-1]
        return (
            f"({tone}) You said: '{user_msg}'. Right now I can see {visible_text}. "
            f"My energy is {phys.energy:.2f}, stress {phys.stress_load:.2f}. "
            f"I am prioritizing '{goal_name}' while currently '{action_name}'. "
            f"Recent memory: {memory_hint}."
        )

    return (
        f"({tone}) I currently observe {visible_text}. "
        f"Goal='{goal_name}', action='{action_name}', "
        f"energy={phys.energy:.2f}, stamina={phys.stamina:.2f}."
    )


# -----------------------------
# Simulation engine
# -----------------------------


class SimulationEngine:
    def __init__(self) -> None:
        self.world = self._create_initial_world()

    def _create_initial_world(self) -> WorldState:
        demo_agent = AgentState(
            id="agent-1",
            name="Rico",
            position=(0.0, 0.0),
            facing_radians=0.0,
        )
        demo_agent.emotional_state.dimensions = {
            "engagement": EmotionalDimension(0.4, 0.03),
            "anxiety": EmotionalDimension(0.1, 0.05),
            "fatigue": EmotionalDimension(0.2, 0.02),
            "irritation": EmotionalDimension(0.05, 0.06),
        }

        # Secondary agent included to keep multi-agent model first-class.
        companion = AgentState(
            id="agent-2",
            name="Nova",
            position=(4.0, 1.5),
            facing_radians=pi,
        )
        companion.emotional_state.dimensions = {
            "engagement": EmotionalDimension(0.3, 0.03),
            "anxiety": EmotionalDimension(0.1, 0.05),
            "fatigue": EmotionalDimension(0.1, 0.02),
        }

        objects = {
            "obj-1": WorldObject(id="obj-1", name="Info Kiosk", kind="kiosk", position=(3.0, 0.0)),
            "obj-2": WorldObject(id="obj-2", name="Charging Bench", kind="bench", position=(-2.0, -1.0)),
            "obj-3": WorldObject(id="obj-3", name="Snack Station", kind="station", position=(1.0, 3.0)),
        }

        return WorldState(
            time=0.0,
            tick=0,
            agents={demo_agent.id: demo_agent, companion.id: companion},
            objects=objects,
            obstacles=[Obstacle(id="obs-1", kind="pillar", position=(1.5, 1.2), radius=0.4)],
            events=[],
        )

    def queue_user_chat(self, agent_id: str, message: str) -> None:
        agent = self.world.agents.get(agent_id)
        if not agent:
            raise ValueError(f"Unknown agent_id '{agent_id}'")
        agent.pending_user_chat.append(message)

    def tick(self, dt: float = 1.0, steps: int = 1) -> Dict[str, Any]:
        steps = max(1, min(steps, 50))
        dt = clamp(dt, 0.1, 5.0)

        all_responses: List[Dict[str, str]] = []
        new_events: List[Event] = []

        for _ in range(steps):
            self.world.tick += 1
            self.world.time += dt

            for agent in self.world.agents.values():
                # 1) Perception (no omniscient world dump)
                perception = build_perception(self.world, agent)

                # 2) Interpretation
                interpretation = interpret_perception(perception, agent)

                # 3) Emotional/Physical update
                update_emotional_and_physical_state(agent, interpretation, dt)

                # 4) Goal scoring/selection
                scored_goals = score_goals(agent, perception, interpretation)
                select_goal(agent, scored_goals)

                # 5) Plan/action selection
                agent.current_action = select_plan_and_action(agent, perception, interpretation)

                # 6) Execute action with spatial/time progression
                execution_events = execute_action(self.world, agent, dt)

                # 7) Memory update
                update_memory(self.world, agent, perception, interpretation)

                # 8) Response generation
                response = generate_grounded_response(agent, perception, interpretation)
                agent.last_response = response
                all_responses.append({"agent_id": agent.id, "response": response})

                # User chat consumed after this loop iteration
                agent.pending_user_chat = []

                if execution_events:
                    new_events.extend(execution_events)

            self.world.events.extend(new_events)
            if len(self.world.events) > 500:
                self.world.events = self.world.events[-500:]

        return {
            "time": self.world.time,
            "tick": self.world.tick,
            "responses": all_responses,
            "events_added": [self._event_to_dict(e) for e in new_events],
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

        # No auto tick: immediate minimal acknowledgment grounded in current memory/state.
        agent = self.world.agents[agent_id]
        return {
            "agent_id": agent_id,
            "message": message,
            "response": f"Queued for {agent.name}. Current goal: {agent.current_goal.name if agent.current_goal else 'explore'}.",
            "tick": self.world.tick,
            "time": self.world.time,
        }

    def get_state(self) -> Dict[str, Any]:
        return {
            "time": self.world.time,
            "tick": self.world.tick,
            "agents": {agent_id: self._agent_to_dict(agent) for agent_id, agent in self.world.agents.items()},
            "objects": {obj_id: self._object_to_dict(obj) for obj_id, obj in self.world.objects.items()},
            "obstacles": [self._obstacle_to_dict(o) for o in self.world.obstacles],
            "events": [self._event_to_dict(e) for e in self.world.events[-100:]],
        }

    @staticmethod
    def _object_to_dict(obj: WorldObject) -> Dict[str, Any]:
        return {
            "id": obj.id,
            "name": obj.name,
            "kind": obj.kind,
            "position": list(obj.position),
            "interactable": obj.interactable,
            "properties": obj.properties,
        }

    @staticmethod
    def _obstacle_to_dict(obstacle: Obstacle) -> Dict[str, Any]:
        return {
            "id": obstacle.id,
            "kind": obstacle.kind,
            "position": list(obstacle.position),
            "radius": obstacle.radius,
        }

    @staticmethod
    def _event_to_dict(event: Event) -> Dict[str, Any]:
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
    def _agent_to_dict(agent: AgentState) -> Dict[str, Any]:
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
                k: {"intensity": v.intensity, "decay_per_tick": v.decay_per_tick}
                for k, v in agent.emotional_state.dimensions.items()
            },
            "current_goal": {
                "name": agent.current_goal.name,
                "score": agent.current_goal.score,
                "urgency": agent.current_goal.urgency,
                "reason": agent.current_goal.reason,
            }
            if agent.current_goal
            else None,
            "goals": [
                {"name": g.name, "score": g.score, "urgency": g.urgency, "reason": g.reason}
                for g in agent.goals
            ],
            "current_plan": agent.current_plan,
            "current_action": {
                "kind": agent.current_action.kind,
                "status": agent.current_action.status,
                "target_id": agent.current_action.target_id,
                "target_position": list(agent.current_action.target_position)
                if agent.current_action.target_position
                else None,
                "elapsed": agent.current_action.elapsed,
                "duration": agent.current_action.duration,
                "metadata": agent.current_action.metadata,
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
