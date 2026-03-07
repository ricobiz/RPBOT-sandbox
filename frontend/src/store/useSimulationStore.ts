import { create } from 'zustand'
// rewritten simulation store

const DEFAULT_LOCAL_BACKEND_URL = 'http://127.0.0.1:8000'

export type Vector3 = [number, number, number]

export type SimActionState = 'idle' | 'walk' | 'interact' | 'orient'

export type WorldEntity = {
  id: string
  name: string
  type: string
  position: Vector3
  velocity?: Vector3
  distance?: number
  status?: string
}

export type AgentSnapshot = {
  id: string
  name: string
  position: Vector3
  orientation: number
  currentAction: SimActionState
  targetEntityId?: string
}

export type EmotionState = {
  name: string
  intensity: number
}

export type PhysicalCondition = {
  energy: number
  stamina: number
  stress: number
  health: number
}

export type GoalState = {
  text: string
  priority: 'low' | 'medium' | 'high'
}

export type PlanState = {
  steps: string[]
  currentStepIndex: number
  currentAction: string
}

export type MemoryUpdate = {
  id: string
  tick: number
  timestamp: string
  type: 'observation' | 'decision' | 'interaction' | 'reflection'
  content: string
}

export type InteractionEvent = {
  id: string
  tick: number
  timestamp: string
  with: string
  summary: string
}

export type GroundedChatMessage = {
  id: string
  role: 'user' | 'agent' | 'system'
  tick: number
  timestamp: string
  content: string
  grounding?: string
}

export type SimulationSnapshot = {
  tick: number
  timeSeconds: number
  paused: boolean
  world: {
    sceneId: string
    entities: WorldEntity[]
  }
  agent: AgentSnapshot
  perceivedNearby: WorldEntity[]
  emotions: EmotionState[]
  physicalCondition: PhysicalCondition
  goal: GoalState
  plan: PlanState
  recentMemoryUpdates: MemoryUpdate[]
  interactionHistory: InteractionEvent[]
  chatMessages: GroundedChatMessage[]
}

type SimulationStore = {
  snapshot: SimulationSnapshot | null
  agentPath: Vector3[]
  selectedEntityId: string | null
  loading: boolean
  isAdvancing: boolean
  isSendingChat: boolean
  error: string | null
  loadInitialState: () => Promise<void>
  advanceTicks: (steps?: number) => Promise<void>
  sendGroundedChat: (message: string) => Promise<void>
  togglePause: () => Promise<void>
  selectEntity: (entityId: string | null) => void
}

const nowIso = () => new Date().toISOString()
const makeId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value))

const toNumber = (value: unknown, fallback = 0) => (typeof value === 'number' && Number.isFinite(value) ? value : fallback)
const toMaybeNumber = (value: unknown) => (typeof value === 'number' && Number.isFinite(value) ? value : undefined)

const toIso = (value: unknown) => {
  if (typeof value === 'string') return value
  if (typeof value === 'number') {
    const ms = value > 1_000_000_000_000 ? value : value * 1000
    return new Date(ms).toISOString()
  }
  return nowIso()
}

const toVector3 = (value: unknown, fallback: Vector3 = [0, 0, 0]): Vector3 => {
  if (!Array.isArray(value)) return fallback
  const x = toNumber(value[0], fallback[0])
  const z = toNumber(value[1] ?? value[2], fallback[2])
  return [x, 0, z]
}

const mapAction = (kind: unknown): SimActionState => {
  const action = typeof kind === 'string' ? kind.toLowerCase() : ''
  if (action === 'walk' || action === 'interact' || action === 'orient') return action
  return 'idle'
}

const mapPriority = (urgency: unknown): GoalState['priority'] => {
  const value = toNumber(urgency, 0)
  if (value >= 0.66) return 'high'
  if (value >= 0.33) return 'medium'
  return 'low'
}

const mapMemoryType = (category: unknown): MemoryUpdate['type'] => {
  const text = typeof category === 'string' ? category.toLowerCase() : ''
  if (text.includes('interact') || text.includes('chat')) return 'interaction'
  if (text.includes('goal') || text.includes('plan') || text.includes('decision')) return 'decision'
  if (text.includes('reflect') || text.includes('summary')) return 'reflection'
  return 'observation'
}

const distanceXZ = (a: Vector3, b: Vector3) => {
  const dx = a[0] - b[0]
  const dz = a[2] - b[2]
  return Math.sqrt(dx * dx + dz * dz)
}

const normalizeBackendUrl = (value: string) => value.trim().replace(/\/+$/, '')

const getBackendBaseUrl = () => {
  const envValue = process.env.NEXT_PUBLIC_BACKEND_URL
  if (envValue && envValue.trim()) return normalizeBackendUrl(envValue)

  if (typeof window === 'undefined') return DEFAULT_LOCAL_BACKEND_URL

  const { protocol, hostname } = window.location
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return `${protocol}//${hostname}:8000`
  }

  return ''
}

const buildApiUrl = (path: string) => {
  const base = getBackendBaseUrl()
  if (base) return `${base}${path}`

  if (typeof window !== 'undefined') {
    return `${window.location.origin}${path}`
  }

  return `${DEFAULT_LOCAL_BACKEND_URL}${path}`
}

const createFallbackSnapshot = (): SimulationSnapshot => ({
  tick: 0,
  timeSeconds: 0,
  paused: false,
  world: {
    sceneId: 'default',
    entities: [
      { id: 'console', name: 'Console', type: 'terminal', position: [1.4, 0, -0.5] },
      { id: 'crate', name: 'Crate', type: 'container', position: [-1.3, 0, 1.2] },
    ],
  },
  agent: {
    id: 'agent-1',
    name: 'RPBOT Agent',
    position: [0, 0, 0],
    orientation: 0,
    currentAction: 'idle',
    targetEntityId: 'console',
  },
  perceivedNearby: [
    { id: 'console', name: 'Console', type: 'terminal', position: [1.4, 0, -0.5], distance: 1.5, status: 'visible' },
    { id: 'crate', name: 'Crate', type: 'container', position: [-1.3, 0, 1.2], distance: 1.7, status: 'visible' },
  ],
  emotions: [{ name: 'focus', intensity: 0.6 }],
  physicalCondition: {
    energy: 0.82,
    stamina: 0.8,
    stress: 0.2,
    health: 0.9,
  },
  goal: {
    text: 'Observe environment and wait for user instruction.',
    priority: 'medium',
  },
  plan: {
    steps: ['Observe scene', 'Respond to chat'],
    currentStepIndex: 0,
    currentAction: 'idle',
  },
  recentMemoryUpdates: [
    {
      id: makeId(),
      tick: 0,
      timestamp: nowIso(),
      type: 'reflection',
      content: 'Fallback mode active until backend is reachable.',
    },
  ],
  interactionHistory: [],
  chatMessages: [
    {
      id: makeId(),
      role: 'system',
      tick: 0,
      timestamp: nowIso(),
      content: 'Initialized with fallback data.',
      grounding: 'tick 0 • fallback',
    },
  ],
})

const dedupeMessages = (items: GroundedChatMessage[]) => {
  const seen = new Set<string>()
  return items.filter((item) => {
    const key = `${item.role}-${item.tick}-${item.content}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

const appendPath = (current: Vector3[], position: Vector3) => {
  const last = current[current.length - 1]
  if (last && last[0] === position[0] && last[1] === position[1] && last[2] === position[2]) return current
  return [...current, position].slice(-120)
}

const unwrapResponseState = (raw: any) => raw?.state || raw?.data?.state || raw || {}

const fromBackend = (rawResponse: any, previous?: SimulationSnapshot): SimulationSnapshot => {
  const base = previous || createFallbackSnapshot()
  const raw = unwrapResponseState(rawResponse)

  const objects = raw?.objects && typeof raw.objects === 'object' ? raw.objects : {}
  const objectEntities: WorldEntity[] = Object.entries(objects).map(([id, object]: [string, any]) => ({
    id,
    name: object?.name || id,
    type: object?.kind || 'object',
    position: toVector3(object?.position),
    status: object?.interactable ? 'interactable' : 'observed',
  }))

  const agents = raw?.agents && typeof raw.agents === 'object' ? raw.agents : {}
  const availableAgentIds = Object.keys(agents)
  const agentId = base.agent.id && agents[base.agent.id] ? base.agent.id : availableAgentIds[0] || base.agent.id
  const backendAgent = agents[agentId] || {}
  const agentPosition = toVector3(backendAgent?.position, base.agent.position)

  const otherAgents: WorldEntity[] = availableAgentIds
    .filter((id) => id !== agentId)
    .map((id) => {
      const other = agents[id]
      return {
        id,
        name: other?.name || id,
        type: 'agent',
        position: toVector3(other?.position),
        status: 'visible',
      }
    })

  const worldEntities = [...objectEntities, ...otherAgents]

  const perception = raw?.perception || raw?.perceptions?.[agentId]
  const perceivedNearby: WorldEntity[] = Array.isArray(perception?.nearby_visible_objects)
    ? perception.nearby_visible_objects.map((object: any) => ({
        id: object?.id || makeId(),
        name: object?.name || object?.id || 'object',
        type: object?.kind || object?.type || 'object',
        position: toVector3(object?.position),
        distance: toMaybeNumber(object?.distance),
        status: 'visible',
      }))
    : worldEntities
        .map((entity) => ({
          ...entity,
          distance: distanceXZ(agentPosition, entity.position),
          status: 'in-world',
        }))
        .sort((a, b) => (a.distance || 0) - (b.distance || 0))
        .slice(0, 8)

  const emotionMap = backendAgent?.emotional_state && typeof backendAgent.emotional_state === 'object'
    ? backendAgent.emotional_state
    : null

  const emotions: EmotionState[] = emotionMap
    ? Object.entries(emotionMap).map(([name, value]: [string, any]) => ({
        name,
        intensity: clamp(toNumber(value?.intensity, 0), 0, 1),
      }))
    : base.emotions

  const physical = backendAgent?.physical_state || {}
  const stress = clamp(toNumber(physical?.stress_load, base.physicalCondition.stress), 0, 1)
  const hunger = clamp(toNumber(physical?.hunger, 0.2), 0, 1)

  const physicalCondition: PhysicalCondition = {
    energy: clamp(toNumber(physical?.energy, base.physicalCondition.energy), 0, 1),
    stamina: clamp(toNumber(physical?.stamina, base.physicalCondition.stamina), 0, 1),
    stress,
    health: clamp(1 - hunger * 0.4 - stress * 0.3, 0, 1),
  }

  const currentGoal = backendAgent?.current_goal || {}
  const goal: GoalState = {
    text: currentGoal?.name || currentGoal?.reason || base.goal.text,
    priority: mapPriority(currentGoal?.urgency),
  }

  const currentAction = backendAgent?.current_action || {}
  const planSteps = Array.isArray(backendAgent?.current_plan) ? backendAgent.current_plan : base.plan.steps

  const plan: PlanState = {
    steps: planSteps,
    currentStepIndex: clamp(toNumber(currentAction?.elapsed, base.plan.currentStepIndex), 0, Math.max(planSteps.length - 1, 0)),
    currentAction: (typeof currentAction?.kind === 'string' && currentAction.kind) || base.plan.currentAction,
  }

  const memoryItems = Array.isArray(backendAgent?.memory) ? backendAgent.memory : []
  const recentMemoryUpdates: MemoryUpdate[] = memoryItems.slice(-30).map((memory: any, index: number) => ({
    id: `${agentId}-memory-${memory?.tick ?? 0}-${index}`,
    tick: toNumber(memory?.tick, base.tick),
    timestamp: toIso(memory?.timestamp),
    type: mapMemoryType(memory?.category),
    content: memory?.content || 'Memory update',
  }))

  const events = Array.isArray(raw?.events) ? raw.events : []
  const interactionHistory: InteractionEvent[] = events.slice(-30).map((event: any, index: number) => ({
    id: event?.id || `${agentId}-event-${event?.tick ?? 0}-${index}`,
    tick: toNumber(event?.tick, base.tick),
    timestamp: toIso(event?.timestamp),
    with: event?.source_agent_id || event?.target_id || 'world',
    summary: event?.content || event?.event_type || 'event',
  }))

  const next: SimulationSnapshot = {
    tick: toNumber(raw?.tick ?? rawResponse?.tick, base.tick),
    timeSeconds: toNumber(raw?.time ?? rawResponse?.time, base.timeSeconds),
    paused: base.paused,
    world: {
      sceneId: raw?.scene_id || 'default',
      entities: worldEntities.length ? worldEntities : base.world.entities,
    },
    agent: {
      id: agentId,
      name: backendAgent?.name || base.agent.name,
      position: agentPosition,
      orientation: toNumber(backendAgent?.facing_radians, base.agent.orientation),
      currentAction: mapAction(currentAction?.kind),
      targetEntityId: currentAction?.target_id || base.agent.targetEntityId,
    },
    perceivedNearby: perceivedNearby.length ? perceivedNearby : base.perceivedNearby,
    emotions: emotions.length ? emotions : base.emotions,
    physicalCondition,
    goal,
    plan,
    recentMemoryUpdates: recentMemoryUpdates.length ? recentMemoryUpdates : base.recentMemoryUpdates,
    interactionHistory: interactionHistory.length ? interactionHistory : base.interactionHistory,
    chatMessages: base.chatMessages,
  }

  const backendReply = typeof backendAgent?.last_response === 'string' ? backendAgent.last_response.trim() : ''
  if (backendReply) {
    next.chatMessages = dedupeMessages([
      ...base.chatMessages,
      {
        id: makeId(),
        role: 'agent',
        tick: next.tick,
        timestamp: nowIso(),
        content: backendReply,
        grounding: `tick ${next.tick} • ${next.world.sceneId}`,
      },
    ])
  }

  return next
}

const fallbackTickAdvance = (snapshot: SimulationSnapshot, steps: number): SimulationSnapshot => {
  let next = { ...snapshot }

  for (let i = 0; i < steps; i += 1) {
    const tick = next.tick + 1
    const target = next.perceivedNearby[tick % Math.max(next.perceivedNearby.length, 1)]
    const cycle: SimActionState[] = ['orient', 'walk', 'interact', 'idle']
    const action = cycle[tick % cycle.length]

    const moved: Vector3 = [...next.agent.position]
    if (action === 'walk' && target) {
      moved[0] += (target.position[0] - moved[0]) * 0.2
      moved[2] += (target.position[2] - moved[2]) * 0.2
    }

    next = {
      ...next,
      tick,
      timeSeconds: next.timeSeconds + 1,
      agent: {
        ...next.agent,
        position: moved,
        currentAction: action,
        targetEntityId: target?.id,
      },
      plan: {
        ...next.plan,
        currentStepIndex: tick % Math.max(next.plan.steps.length, 1),
        currentAction: action,
      },
      emotions: next.emotions.map((emotion) => ({
        ...emotion,
        intensity: clamp(emotion.intensity + (Math.random() - 0.5) * 0.06, 0, 1),
      })),
      physicalCondition: {
        ...next.physicalCondition,
        energy: clamp(next.physicalCondition.energy - 0.02, 0, 1),
        stamina: clamp(next.physicalCondition.stamina - 0.015, 0, 1),
        stress: clamp(next.physicalCondition.stress + (action === 'interact' ? 0.02 : -0.01), 0, 1),
      },
      recentMemoryUpdates: [
        ...next.recentMemoryUpdates.slice(-24),
        {
          id: makeId(),
          tick,
          timestamp: nowIso(),
          type: 'observation',
          content: `Fallback tick ${tick}: action ${action}${target ? ` near ${target.name}` : ''}`,
        },
      ],
    }
  }

  return next
}

const fallbackReply = (snapshot: SimulationSnapshot, userMessage: string) => {
  const nearest = snapshot.perceivedNearby[0]
  return `Received "${userMessage}". Tick ${snapshot.tick}, action ${snapshot.agent.currentAction}, nearest ${nearest?.name || 'none'}.`
}

const requestJson = async (path: string, init?: RequestInit): Promise<any> => {
  const response = await fetch(buildApiUrl(path), {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  })

  if (!response.ok) {
    throw new Error(`Backend request failed (${response.status} ${response.statusText})`)
  }

  return response.json()
}

export const useSimulationStore = create<SimulationStore>((set, get) => ({
  snapshot: null,
  agentPath: [],
  selectedEntityId: null,
  loading: false,
  isAdvancing: false,
  isSendingChat: false,
  error: null,

  loadInitialState: async () => {
    set({ loading: true, error: null })

    try {
      const response = await requestJson('/simulation/state')
      const snapshot = fromBackend(response, get().snapshot || undefined)
      set({
        snapshot,
        agentPath: [snapshot.agent.position],
        loading: false,
        error: null,
      })
    } catch (error) {
      const fallback = get().snapshot || createFallbackSnapshot()
      const message = error instanceof Error ? error.message : 'Unable to load initial state'
      set((state) => ({
        snapshot: fallback,
        agentPath: state.agentPath.length ? state.agentPath : [fallback.agent.position],
        loading: false,
        error: `Backend unavailable. ${message}`,
      }))
    }
  },

  advanceTicks: async (steps = 1) => {
    const safeSteps = Math.max(1, Math.floor(steps))
    const current = get().snapshot || createFallbackSnapshot()

    if (current.paused) return

    set({ isAdvancing: true, error: null, snapshot: current })

    try {
      const response = await requestJson('/simulation/tick', {
        method: 'POST',
        body: JSON.stringify({ dt: 1, steps: safeSteps }),
      })

      const snapshot = fromBackend(response, get().snapshot || current)
      set((state) => ({
        snapshot,
        isAdvancing: false,
        error: null,
        agentPath: appendPath(state.agentPath, snapshot.agent.position),
      }))
    } catch (error) {
      const snapshot = fallbackTickAdvance(current, safeSteps)
      const message = error instanceof Error ? error.message : 'Unable to advance simulation'
      set((state) => ({
        snapshot,
        isAdvancing: false,
        error: `Tick used fallback mode. ${message}`,
        agentPath: appendPath(state.agentPath, snapshot.agent.position),
      }))
    }
  },

  sendGroundedChat: async (message: string) => {
    const content = message.trim()
    if (!content) return

    const current = get().snapshot || createFallbackSnapshot()
    const userMessage: GroundedChatMessage = {
      id: makeId(),
      role: 'user',
      tick: current.tick,
      timestamp: nowIso(),
      content,
      grounding: `tick ${current.tick} • ${current.world.sceneId}`,
    }

    set((state) => ({
      snapshot: state.snapshot
        ? { ...state.snapshot, chatMessages: [...state.snapshot.chatMessages, userMessage] }
        : { ...current, chatMessages: [...current.chatMessages, userMessage] },
      isSendingChat: true,
      error: null,
    }))

    try {
      const response = await requestJson('/simulation/chat', {
        method: 'POST',
        body: JSON.stringify({
          message: content,
          agent_id: current.agent.id,
          auto_tick: true,
        }),
      })

      const snapshot = fromBackend(response, get().snapshot || current)
      const responseText = typeof response?.response === 'string' ? response.response.trim() : ''
      const assistantMessage = responseText
        ? {
            id: makeId(),
            role: 'agent' as const,
            tick: snapshot.tick,
            timestamp: nowIso(),
            content: responseText,
            grounding: `tick ${snapshot.tick} • ${snapshot.world.sceneId}`,
          }
        : null

      set((state) => ({
        snapshot: {
          ...snapshot,
          chatMessages: dedupeMessages([
            ...(state.snapshot?.chatMessages || snapshot.chatMessages),
            ...(assistantMessage ? [assistantMessage] : []),
          ]),
        },
        isSendingChat: false,
        error: null,
        agentPath: appendPath(state.agentPath, snapshot.agent.position),
      }))
    } catch (error) {
      const base = get().snapshot || current
      const localReply: GroundedChatMessage = {
        id: makeId(),
        role: 'agent',
        tick: base.tick,
        timestamp: nowIso(),
        content: fallbackReply(base, content),
        grounding: `fallback • tick ${base.tick}`,
      }

      const messageText = error instanceof Error ? error.message : 'Unable to send chat'
      set((state) => ({
        snapshot: state.snapshot
          ? { ...state.snapshot, chatMessages: [...state.snapshot.chatMessages, localReply] }
          : { ...base, chatMessages: [...base.chatMessages, localReply] },
        isSendingChat: false,
        error: `Chat sent in fallback mode. ${messageText}`,
      }))
    }
  },

  togglePause: async () => {
    set((state) => {
      if (!state.snapshot) return state
      return {
        snapshot: {
          ...state.snapshot,
          paused: !state.snapshot.paused,
        },
      }
    })
  },

  selectEntity: (entityId: string | null) => set({ selectedEntityId: entityId }),
}))
