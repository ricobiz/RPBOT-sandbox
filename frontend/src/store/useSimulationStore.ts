import { create } from 'zustand'

const DEFAULT_LOCAL_BACKEND_URL = 'http://127.0.0.1:8000'

type BackendPayload = Record<string, any>

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
const makeId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
const clamp = (value: number, min = 0, max = 1) => Math.max(min, Math.min(max, value))

const toNumber = (value: unknown, fallback = 0) =>
  typeof value === 'number' && Number.isFinite(value) ? value : fallback

const toMaybeNumber = (value: unknown) =>
  typeof value === 'number' && Number.isFinite(value) ? value : undefined

const toIso = (value: unknown) => {
  if (typeof value === 'string' && value.trim()) return value
  if (typeof value === 'number' && Number.isFinite(value)) {
    const millis = value > 1_000_000_000_000 ? value : value * 1000
    return new Date(millis).toISOString()
  }
  return nowIso()
}

const toVector3 = (value: unknown, fallback: Vector3 = [0, 0, 0]): Vector3 => {
  if (!Array.isArray(value)) return fallback
  const x = toNumber(value[0], fallback[0])
  const z = toNumber(value[1] ?? value[2], fallback[2])
  return [x, 0, z]
}

const distanceXZ = (a: Vector3, b: Vector3) => {
  const dx = a[0] - b[0]
  const dz = a[2] - b[2]
  return Math.sqrt(dx * dx + dz * dz)
}

const normalizeBackendUrl = (value: string) => {
  const trimmed = value.trim().replace(/\/+$/, '')
  if (!trimmed) return ''

  try {
    const parsed = new URL(trimmed)
    parsed.protocol = parsed.protocol.toLowerCase()
    parsed.hostname = parsed.hostname.toLowerCase()
    return parsed.toString().replace(/\/+$/, '')
  } catch {
    return trimmed.toLowerCase()
  }
}

const getBackendBaseUrl = () => {
  const envValue = process.env.NEXT_PUBLIC_BACKEND_URL
  if (envValue && envValue.trim()) return normalizeBackendUrl(envValue)

  if (typeof window === 'undefined') return DEFAULT_LOCAL_BACKEND_URL

  const { protocol, hostname } = window.location
  const lowerHost = hostname.toLowerCase()

  if (lowerHost === 'localhost' || lowerHost === '127.0.0.1') {
    return `${protocol}//${lowerHost}:8000`
  }

  return ''
}

const buildApiUrl = (path: string) => {
  const base = getBackendBaseUrl()
  if (base) return `${base}${path}`

  if (typeof window !== 'undefined') return `${window.location.origin}${path}`

  return `${DEFAULT_LOCAL_BACKEND_URL}${path}`
}

const requestJson = async (path: string, init?: RequestInit) => {
  const response = await fetch(buildApiUrl(path), {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed: ${response.status}`)
  }

  return (await response.json()) as BackendPayload
}

const mapAction = (value: unknown): SimActionState => {
  const action = typeof value === 'string' ? value.toLowerCase() : ''
  if (action.includes('walk') || action.includes('move')) return 'walk'
  if (action.includes('interact') || action.includes('gather') || action.includes('respond')) return 'interact'
  if (action.includes('orient') || action.includes('scan') || action.includes('observe')) return 'orient'
  return 'idle'
}

const mapPriority = (value: unknown): GoalState['priority'] => {
  const numeric = toNumber(value, 0)
  if (numeric >= 0.66) return 'high'
  if (numeric >= 0.33) return 'medium'
  return 'low'
}

const mapMemoryType = (value: unknown): MemoryUpdate['type'] => {
  const text = typeof value === 'string' ? value.toLowerCase() : ''
  if (text.includes('interact') || text.includes('chat') || text.includes('message')) return 'interaction'
  if (text.includes('goal') || text.includes('plan') || text.includes('decision')) return 'decision'
  if (text.includes('reflect') || text.includes('summary')) return 'reflection'
  return 'observation'
}

const dedupeMessages = (items: GroundedChatMessage[]) => {
  const seen = new Set<string>()
  return items.filter((item) => {
    const key = `${item.role}-${item.tick}-${item.content}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

const appendPath = (path: Vector3[], next: Vector3) => {
  const last = path[path.length - 1]
  if (last && last[0] === next[0] && last[2] === next[2]) return path
  return [...path, next].slice(-140)
}

const unwrapState = (raw: BackendPayload) => raw?.state || raw?.data?.state || raw

const fromBackend = (rawResponse: BackendPayload, previous: SimulationSnapshot | null): SimulationSnapshot => {
  const raw = unwrapState(rawResponse)

  const tick = toNumber(raw?.tick, previous?.tick || 0)
  const timeSeconds = toNumber(raw?.time, previous?.timeSeconds || 0)

  const agentsRaw = raw?.agents && typeof raw.agents === 'object' ? raw.agents : {}
  const agentIds = Object.keys(agentsRaw)
  const activeAgentId =
    (previous?.agent.id && agentsRaw[previous.agent.id] ? previous.agent.id : undefined) ||
    agentIds[0] ||
    previous?.agent.id ||
    'agent-1'

  const backendAgent = agentsRaw[activeAgentId] || {}
  const agentPosition = toVector3(backendAgent?.position, previous?.agent.position || [0, 0, 0])
  const currentAction = mapAction(backendAgent?.current_action?.name)

  const objectsRaw = raw?.objects && typeof raw.objects === 'object' ? raw.objects : {}
  const objectEntities: WorldEntity[] = Object.entries(objectsRaw).map(([id, object]: [string, any]) => ({
    id,
    name: object?.name || id,
    type: object?.kind || 'object',
    position: toVector3(object?.position),
    status: object?.metadata?.interactable ? 'interactable' : 'inert',
  }))

  const otherAgents: WorldEntity[] = Object.entries(agentsRaw)
    .filter(([id]) => id !== activeAgentId)
    .map(([id, other]: [string, any]) => ({
      id,
      name: other?.name || id,
      type: 'agent',
      position: toVector3(other?.position),
      status: 'visible',
    }))

  const worldEntities = [...objectEntities, ...otherAgents]

  const perception = backendAgent?.last_perception || {}
  const visibleObjects = Array.isArray(perception?.visible_objects) ? perception.visible_objects : []
  const visibleAgents = Array.isArray(perception?.visible_agents) ? perception.visible_agents : []

  const perceivedNearby: WorldEntity[] = [
    ...visibleObjects.map((item: any) => ({
      id: item?.id || makeId(),
      name: item?.name || item?.id || 'object',
      type: item?.kind || item?.type || 'object',
      position: toVector3(item?.position),
      distance: toMaybeNumber(item?.distance),
      status: 'visible',
    })),
    ...visibleAgents.map((item: any) => ({
      id: item?.id || makeId(),
      name: item?.name || item?.id || 'agent',
      type: 'agent',
      position: toVector3(item?.position),
      distance: toMaybeNumber(item?.distance),
      status: 'visible',
    })),
  ]

  const withComputedDistance = (perceivedNearby.length ? perceivedNearby : worldEntities).map((entity) => ({
    ...entity,
    distance: entity.distance ?? distanceXZ(agentPosition, entity.position),
  }))

  const sortedNearby = withComputedDistance.sort((a, b) => (a.distance || 0) - (b.distance || 0)).slice(0, 10)

  const emotionalState =
    backendAgent?.emotional_state && typeof backendAgent.emotional_state === 'object'
      ? backendAgent.emotional_state
      : null

  const emotions: EmotionState[] = emotionalState
    ? Object.entries(emotionalState).map(([name, intensity]) => ({
        name,
        intensity: clamp(toNumber(intensity, 0)),
      }))
    : []

  const physical = backendAgent?.physical_state || {}
  const stress = clamp(toNumber(physical?.stress, previous?.physicalCondition.stress ?? 0.2))
  const hunger = clamp(toNumber(physical?.hunger, 0.2))

  const physicalCondition: PhysicalCondition = {
    energy: clamp(toNumber(physical?.energy, previous?.physicalCondition.energy ?? 0.8)),
    stamina: clamp(toNumber(physical?.stamina, previous?.physicalCondition.stamina ?? 0.8)),
    stress,
    health: clamp(1 - (stress * 0.6 + hunger * 0.4)),
  }

  const currentGoal = backendAgent?.current_goal || {}
  const currentPlan = backendAgent?.current_plan || {}

  const memoryItems = Array.isArray(backendAgent?.memory) ? backendAgent.memory : []
  const recentMemoryUpdates: MemoryUpdate[] = memoryItems.slice(-40).map((item: any) => ({
    id: String(item?.id || makeId()),
    tick: toNumber(item?.tick, tick),
    timestamp: toIso(item?.time),
    type: mapMemoryType(item?.category),
    content: String(item?.content || ''),
  }))

  const events = Array.isArray(raw?.recent_events) ? raw.recent_events : []
  const interactionHistory: InteractionEvent[] = events
    .filter((event: any) => {
      const kind = String(event?.event_type || '').toLowerCase()
      return kind.includes('interaction') || kind.includes('user_message') || kind.includes('agent_response')
    })
    .slice(-40)
    .map((event: any) => ({
      id: String(event?.id || makeId()),
      tick: toNumber(event?.tick, tick),
      timestamp: toIso(event?.time),
      with: String(event?.source_agent_id || event?.target_id || 'world'),
      summary: String(event?.content || event?.event_type || 'interaction'),
    }))

  const eventChatMessages: GroundedChatMessage[] = events
    .filter((event: any) => {
      const kind = String(event?.event_type || '').toLowerCase()
      return kind === 'user_message' || kind === 'agent_response'
    })
    .map((event: any) => {
      const kind = String(event?.event_type || '').toLowerCase()
      return {
        id: String(event?.id || makeId()),
        role: (kind === 'user_message' ? 'user' : 'agent') as GroundedChatMessage['role'],
        tick: toNumber(event?.tick, tick),
        timestamp: toIso(event?.time),
        content: String(event?.content || ''),
        grounding: `tick ${toNumber(event?.tick, tick)}`,
      }
    })

  const chatMessages = dedupeMessages([...(previous?.chatMessages || []), ...eventChatMessages]).slice(-60)

  const targetEntityId = sortedNearby[0]?.id

  return {
    tick,
    timeSeconds,
    paused: previous?.paused ?? false,
    world: {
      sceneId: String(raw?.scene_id || 'default'),
      entities: worldEntities,
    },
    agent: {
      id: activeAgentId,
      name: backendAgent?.name || previous?.agent.name || activeAgentId,
      position: agentPosition,
      orientation: toNumber(backendAgent?.facing_radians, previous?.agent.orientation || 0),
      currentAction,
      targetEntityId,
    },
    perceivedNearby: sortedNearby,
    emotions,
    physicalCondition,
    goal: {
      text: String(currentGoal?.name || 'idle'),
      priority: mapPriority(currentGoal?.priority),
    },
    plan: {
      steps: Array.isArray(currentPlan?.steps) ? currentPlan.steps.map((step: unknown) => String(step)) : [],
      currentStepIndex: toNumber(currentPlan?.cursor, 0),
      currentAction: String(backendAgent?.current_action?.name || 'idle'),
    },
    recentMemoryUpdates,
    interactionHistory,
    chatMessages,
  }
}

const getErrorMessage = (error: unknown) => {
  if (error instanceof Error && error.message) return error.message
  return 'Unable to reach simulation backend.'
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
      const payload = await requestJson('/api/state')
      const snapshot = fromBackend(payload, get().snapshot)
      set({
        snapshot,
        agentPath: [snapshot.agent.position],
        selectedEntityId: snapshot.agent.targetEntityId || null,
        loading: false,
        error: null,
      })
    } catch (error) {
      set({ loading: false, error: getErrorMessage(error) })
    }
  },

  advanceTicks: async (steps = 1) => {
    const { snapshot, isAdvancing } = get()
    if (isAdvancing || snapshot?.paused) return

    if (!snapshot) {
      await get().loadInitialState()
      return
    }

    set({ isAdvancing: true, error: null })

    try {
      const payload = await requestJson('/api/tick', {
        method: 'POST',
        body: JSON.stringify({ dt: 1, steps: Math.max(1, Math.min(120, Math.round(steps))) }),
      })

      const next = fromBackend(payload, get().snapshot)

      set((state) => ({
        snapshot: next,
        agentPath: appendPath(state.agentPath, next.agent.position),
        selectedEntityId: state.selectedEntityId,
        isAdvancing: false,
        error: null,
      }))
    } catch (error) {
      set({ isAdvancing: false, error: getErrorMessage(error) })
    }
  },

  sendGroundedChat: async (message: string) => {
    const trimmed = message.trim()
    if (!trimmed) return

    const { snapshot, isSendingChat } = get()
    if (isSendingChat) return

    if (!snapshot) {
      await get().loadInitialState()
      if (!get().snapshot) return
    }

    set({ isSendingChat: true, error: null })

    try {
      const active = get().snapshot
      const payload = await requestJson('/api/chat', {
        method: 'POST',
        body: JSON.stringify({
          agent_id: active?.agent.id || 'agent-1',
          message: trimmed,
          auto_tick: true,
        }),
      })

      const next = fromBackend(payload, get().snapshot)
      const backendReply = typeof payload?.message === 'string' ? payload.message : null

      const injectedReply: GroundedChatMessage[] = backendReply
        ? [
            {
              id: makeId(),
              role: 'agent',
              tick: next.tick,
              timestamp: nowIso(),
              content: backendReply,
              grounding: `tick ${next.tick}`,
            },
          ]
        : []

      set((state) => ({
        snapshot: {
          ...next,
          chatMessages: dedupeMessages([...(next.chatMessages || []), ...injectedReply]).slice(-60),
        },
        agentPath: appendPath(state.agentPath, next.agent.position),
        isSendingChat: false,
        error: null,
      }))
    } catch (error) {
      set({ isSendingChat: false, error: getErrorMessage(error) })
    }
  },

  togglePause: async () => {
    set((state) => {
      if (!state.snapshot) return state
      return {
        ...state,
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
