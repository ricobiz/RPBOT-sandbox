import { create } from 'zustand'

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

const toVector3 = (value: unknown, fallback: Vector3 = [0, 0, 0]): Vector3 => {
  if (!Array.isArray(value)) return fallback
  const x = toNumber(value[0], fallback[0])
  const z = toNumber(value[1] ?? value[2], fallback[2])
  return [x, 0, z]
}

const toIsoString = (value: unknown) => {
  if (typeof value === 'string') return value
  if (typeof value === 'number') {
    const ms = value > 1_000_000_000_000 ? value : value * 1000
    const date = new Date(ms)
    return Number.isNaN(date.getTime()) ? nowIso() : date.toISOString()
  }
  return nowIso()
}

const normalizeBackendBaseUrl = (value: string) => value.trim().replace(/\/+$/, '')

const getBackendBaseUrl = () => {
  const envUrl = process.env.NEXT_PUBLIC_BACKEND_URL
  if (envUrl && envUrl.trim()) {
    return normalizeBackendBaseUrl(envUrl)
  }

  if (typeof window === 'undefined') {
    return DEFAULT_LOCAL_BACKEND_URL
  }

  const { protocol, hostname } = window.location
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return `${protocol}//${hostname}:8000`
  }

  return ''
}

const apiUrl = (path: string) => {
  const base = getBackendBaseUrl()
  return base ? `${base}${path}` : path
}

const createFallbackSnapshot = (): SimulationSnapshot => ({
  tick: 0,
  timeSeconds: 0,
  paused: false,
  world: {
    sceneId: 'default',
    entities: [
      { id: 'object-console', name: 'Console', type: 'terminal', position: [1.5, 0, -0.5] },
      { id: 'object-crate', name: 'Supply Crate', type: 'crate', position: [-1.2, 0, 1.1] },
    ],
  },
  agent: {
    id: 'agent-1',
    name: 'RPBOT Agent',
    position: [0, 0, 0],
    orientation: 0,
    currentAction: 'idle',
    targetEntityId: 'object-console',
  },
  perceivedNearby: [
    { id: 'object-console', name: 'Console', type: 'terminal', position: [1.5, 0, -0.5], distance: 1.6, status: 'visible' },
    { id: 'object-crate', name: 'Supply Crate', type: 'crate', position: [-1.2, 0, 1.1], distance: 1.7, status: 'visible' },
  ],
  emotions: [{ name: 'focus', intensity: 0.6 }],
  physicalCondition: {
    energy: 0.8,
    stamina: 0.78,
    stress: 0.22,
    health: 0.9,
  },
  goal: {
    text: 'Observe the world and wait for user instructions.',
    priority: 'medium',
  },
  plan: {
    steps: ['Observe nearby entities', 'Respond to user'],
    currentStepIndex: 0,
    currentAction: 'idle',
  },
  recentMemoryUpdates: [
    {
      id: makeId(),
      tick: 0,
      timestamp: nowIso(),
      type: 'reflection',
      content: 'Fallback mode active: backend unavailable.',
    },
  ],
  interactionHistory: [],
  chatMessages: [
    {
      id: makeId(),
      role: 'system',
      tick: 0,
      timestamp: nowIso(),
      content: 'Running with local fallback state until backend responds.',
      grounding: 'tick 0',
    },
  ],
})

const mapActionKind = (kind: unknown): SimActionState => {
  const text = typeof kind === 'string' ? kind.toLowerCase() : 'idle'
  if (text === 'walk') return 'walk'
  if (text === 'interact') return 'interact'
  if (text === 'orient') return 'orient'
  return 'idle'
}

const priorityFromUrgency = (urgency: unknown): GoalState['priority'] => {
  const value = toNumber(urgency, 0)
  if (value >= 0.66) return 'high'
  if (value >= 0.33) return 'medium'
  return 'low'
}

const mapMemoryType = (type: unknown): MemoryUpdate['type'] => {
  const text = typeof type === 'string' ? type.toLowerCase() : ''
  if (text.includes('decision') || text.includes('goal')) return 'decision'
  if (text.includes('interact') || text.includes('chat')) return 'interaction'
  if (text.includes('reflect') || text.includes('summary')) return 'reflection'
  return 'observation'
}

const distance3 = (a: Vector3, b: Vector3) => {
  const dx = a[0] - b[0]
  const dz = a[2] - b[2]
  return Math.sqrt(dx * dx + dz * dz)
}

const dedupeChat = (messages: GroundedChatMessage[]) => {
  const seen = new Set<string>()
  return messages.filter((message) => {
    const key = `${message.role}-${message.tick}-${message.content}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

const appendPath = (path: Vector3[], next: Vector3) => {
  const last = path[path.length - 1]
  if (last && last[0] === next[0] && last[1] === next[1] && last[2] === next[2]) return path
  const nextPath = [...path, next]
  return nextPath.slice(-120)
}

const unwrapState = (raw: any) => raw?.state || raw?.data?.state || raw?.data || raw || {}

const fromBackend = (rawResponse: any, previous?: SimulationSnapshot): SimulationSnapshot => {
  const base = previous || createFallbackSnapshot()
  const raw = unwrapState(rawResponse)

  const rawObjects = raw?.objects && typeof raw.objects === 'object' ? raw.objects : {}
  const objectEntities: WorldEntity[] = Object.entries(rawObjects).map(([id, obj]: [string, any]) => ({
    id,
    name: obj?.name || id,
    type: obj?.kind || 'object',
    position: toVector3(obj?.position),
    status: obj?.interactable ? 'interactable' : 'observed',
  }))

  const rawAgents = raw?.agents && typeof raw.agents === 'object' ? raw.agents : {}
  const agentIds = Object.keys(rawAgents)
  const selectedAgentId = base.agent.id && rawAgents[base.agent.id] ? base.agent.id : agentIds[0] || base.agent.id
  const rawAgent = rawAgents[selectedAgentId] || {}

  const agentPosition = toVector3(rawAgent?.position, base.agent.position)
  const worldEntities: WorldEntity[] = [
    ...objectEntities,
    ...agentIds
      .filter((id) => id !== selectedAgentId)
      .map((id) => {
        const other = rawAgents[id]
        return {
          id,
          name: other?.name || id,
          type: 'agent',
          position: toVector3(other?.position),
          status: 'visible',
        }
      }),
  ]

  const rawPerception = raw?.perception || raw?.perceptions?.[selectedAgentId]
  const perceivedNearby: WorldEntity[] = Array.isArray(rawPerception?.nearby_visible_objects)
    ? rawPerception.nearby_visible_objects.map((obj: any) => ({
        id: obj?.id || makeId(),
        name: obj?.name || obj?.id || 'object',
        type: obj?.kind || obj?.type || 'object',
        position: toVector3(obj?.position),
        distance: toNumber(obj?.distance, undefined as unknown as number),
        status: 'visible',
      }))
    : worldEntities
        .map((entity) => ({ ...entity, distance: distance3(agentPosition, entity.position), status: 'in-world' }))
        .sort((a, b) => (a.distance || 0) - (b.distance || 0))
        .slice(0, 8)

  const emotionDimensions = rawAgent?.emotional_state && typeof rawAgent.emotional_state === 'object'
    ? rawAgent.emotional_state
    : null

  const emotions: EmotionState[] = emotionDimensions
    ? Object.entries(emotionDimensions).map(([name, value]: [string, any]) => ({
        name,
        intensity: clamp(toNumber(value?.intensity, 0), 0, 1),
      }))
    : base.emotions

  const physical = rawAgent?.physical_state || {}
  const stress = clamp(toNumber(physical?.stress_load, base.physicalCondition.stress), 0, 1)
  const hunger = clamp(toNumber(physical?.hunger, 0.2), 0, 1)

  const physicalCondition: PhysicalCondition = {
    energy: clamp(toNumber(physical?.energy, base.physicalCondition.energy), 0, 1),
    stamina: clamp(toNumber(physical?.stamina, base.physicalCondition.stamina), 0, 1),
    stress,
    health: clamp(1 - hunger * 0.4 - stress * 0.3, 0, 1),
  }

  const currentGoal = rawAgent?.current_goal || {}
  const goal: GoalState = {
    text: currentGoal?.name || currentGoal?.reason || base.goal.text,
    priority: priorityFromUrgency(currentGoal?.urgency),
  }

  const rawPlanSteps = Array.isArray(rawAgent?.current_plan) ? rawAgent.current_plan : base.plan.steps
  const currentAction = rawAgent?.current_action || {}

  const plan: PlanState = {
    steps: rawPlanSteps,
    currentStepIndex: clamp(toNumber(currentAction?.elapsed, base.plan.currentStepIndex), 0, Math.max(rawPlanSteps.length - 1, 0)),
    currentAction:
      (typeof currentAction?.kind === 'string' && currentAction.kind) ||
      (typeof currentAction?.status === 'string' && currentAction.status) ||
      base.plan.currentAction,
  }

  const memoryRaw = Array.isArray(rawAgent?.memory) ? rawAgent.memory : []
  const recentMemoryUpdates: MemoryUpdate[] = memoryRaw.slice(-30).map((item: any, index: number) => ({
    id: `${selectedAgentId}-memory-${item?.tick ?? base.tick}-${index}-${item?.category || 'observation'}`,
    tick: toNumber(item?.tick, base.tick),
    timestamp: toIsoString(item?.timestamp),
    type: mapMemoryType(item?.category),
    content: item?.content || 'Memory update',
  }))

  const events = Array.isArray(raw?.events) ? raw.events : []
  const interactionHistory: InteractionEvent[] = events.slice(-30).map((event: any, index: number) => ({
    id: event?.id || `${selectedAgentId}-event-${event?.tick ?? base.tick}-${index}`,
    tick: toNumber(event?.tick, base.tick),
    timestamp: toIsoString(event?.timestamp),
    with: event?.source_agent_id || event?.target_id || 'world',
    summary: event?.content || event?.event_type || 'event',
  }))

  const nextSnapshot: SimulationSnapshot = {
    tick: toNumber(raw?.tick ?? rawResponse?.tick, base.tick),
    timeSeconds: toNumber(raw?.time ?? rawResponse?.time, base.timeSeconds),
    paused: base.paused,
    world: {
      sceneId: raw?.scene_id || 'default',
      entities: worldEntities.length ? worldEntities : base.world.entities,
    },
    agent: {
      id: selectedAgentId,
      name: rawAgent?.name || base.agent.name,
      position: agentPosition,
      orientation: toNumber(rawAgent?.facing_radians, base.agent.orientation),
      currentAction: mapActionKind(currentAction?.kind),
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

  const backendReply = typeof rawAgent?.last_response === 'string' ? rawAgent.last_response.trim() : ''
  if (backendReply) {
    nextSnapshot.chatMessages = dedupeChat([
      ...base.chatMessages,
      {
        id: makeId(),
        role: 'agent',
        tick: nextSnapshot.tick,
        timestamp: nowIso(),
        content: backendReply,
        grounding: `tick ${nextSnapshot.tick} • ${nextSnapshot.world.sceneId}`,
      },
    ])
  }

  return nextSnapshot
}

const fallbackTickAdvance = (snapshot: SimulationSnapshot, steps: number): SimulationSnapshot => {
  let next = { ...snapshot }

  for (let i = 0; i < steps; i += 1) {
    const tick = next.tick + 1
    const target = next.perceivedNearby[tick % Math.max(next.perceivedNearby.length, 1)]
    const nextAction: SimActionState[] = ['orient', 'walk', 'interact', 'idle']
    const action = nextAction[tick % nextAction.length]

    const movedPosition: Vector3 = [...next.agent.position]
    if (action === 'walk' && target) {
      movedPosition[0] += (target.position[0] - movedPosition[0]) * 0.2
      movedPosition[2] += (target.position[2] - movedPosition[2]) * 0.2
    }

    next = {
      ...next,
      tick,
      timeSeconds: next.timeSeconds + 1,
      agent: {
        ...next.agent,
        position: movedPosition,
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
        intensity: clamp(emotion.intensity + (Math.random() - 0.5) * 0.05, 0, 1),
      })),
      physicalCondition: {
        ...next.physicalCondition,
        energy: clamp(next.physicalCondition.energy - 0.02, 0, 1),
        stamina: clamp(next.physicalCondition.stamina - 0.01, 0, 1),
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

const fallbackAgentReply = (snapshot: SimulationSnapshot, text: string) => {
  const nearby = snapshot.perceivedNearby[0]
  return `Received: "${text}". Tick ${snapshot.tick}, action ${snapshot.agent.currentAction}, nearest ${nearby?.name || 'none'}.`
}

const requestJson = async (path: string, init?: RequestInit): Promise<any> => {
  const response = await fetch(apiUrl(path), {
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
        loading: false,
        error: null,
        agentPath: [snapshot.agent.position],
      })
    } catch (error) {
      const previous = get().snapshot
      const snapshot = previous || createFallbackSnapshot()
      const message = error instanceof Error ? error.message : 'Unable to load simulation state'
      set({
        snapshot,
        loading: false,
        error: `Backend unavailable. ${message}`,
        agentPath: previous ? get().agentPath : [snapshot.agent.position],
      })
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
      const message = error instanceof Error ? error.message : 'Unable to tick simulation'
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

      const base = get().snapshot || current
      const snapshot = fromBackend(response, base)
      const responseText = typeof response?.response === 'string' ? response.response : ''
      const assistantMessage: GroundedChatMessage | null = responseText
        ? {
            id: makeId(),
            role: 'agent',
            tick: snapshot.tick,
            timestamp: nowIso(),
            content: responseText,
            grounding: `tick ${snapshot.tick} • ${snapshot.world.sceneId}`,
          }
        : null

      set((state) => ({
        snapshot: {
          ...snapshot,
          chatMessages: dedupeChat([
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
        content: fallbackAgentReply(base, content),
        grounding: `fallback • tick ${base.tick}`,
      }

      const messageText = error instanceof Error ? error.message : 'Unable to send chat message'
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

  selectEntity: (entityId: string | null) => {
    set({ selectedEntityId: entityId })
  },
}))
