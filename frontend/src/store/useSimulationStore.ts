import { create } from 'zustand'

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000'

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

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value))

const makeId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

const createFallbackSnapshot = (): SimulationSnapshot => ({
  tick: 0,
  timeSeconds: 0,
  paused: false,
  world: {
    sceneId: 'default',
    entities: [
      { id: 'table-1', name: 'Workbench', type: 'furniture', position: [2, 0, -1] },
      { id: 'crate-1', name: 'Supply Crate', type: 'object', position: [-2, 0, 1] },
    ],
  },
  agent: {
    id: 'robot',
    name: 'RPBOT Agent',
    position: [0, 0, 0],
    orientation: 0,
    currentAction: 'idle',
    targetEntityId: 'table-1',
  },
  perceivedNearby: [
    { id: 'table-1', name: 'Workbench', type: 'furniture', position: [2, 0, -1], distance: 2.2, status: 'reachable' },
    { id: 'crate-1', name: 'Supply Crate', type: 'object', position: [-2, 0, 1], distance: 2.4, status: 'visible' },
  ],
  emotions: [
    { name: 'focus', intensity: 0.82 },
    { name: 'curiosity', intensity: 0.61 },
    { name: 'frustration', intensity: 0.18 },
  ],
  physicalCondition: {
    energy: 0.75,
    stamina: 0.79,
    stress: 0.24,
    health: 0.95,
  },
  goal: {
    text: 'Inspect nearby objects and report useful findings to the operator.',
    priority: 'high',
  },
  plan: {
    steps: ['Orient to target', 'Approach target', 'Inspect target', 'Summarize findings'],
    currentStepIndex: 0,
    currentAction: 'Orienting toward Workbench',
  },
  recentMemoryUpdates: [
    {
      id: makeId(),
      tick: 0,
      timestamp: nowIso(),
      type: 'reflection',
      content: 'Boot complete. Starting baseline environment scan.',
    },
  ],
  interactionHistory: [],
  chatMessages: [
    {
      id: makeId(),
      role: 'system',
      tick: 0,
      timestamp: nowIso(),
      content: 'Simulation initialized.',
      grounding: 'Tick 0 • Scene default',
    },
  ],
})

const requestJson = async (path: string, init?: RequestInit): Promise<any> => {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  })

  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`)
  }

  return response.json()
}

const fromBackend = (raw: any, previous?: SimulationSnapshot): SimulationSnapshot => {
  const base = previous || createFallbackSnapshot()

  const rawScene = raw?.world?.sceneId || raw?.sceneId || 'default'
  const rawTick = typeof raw?.tick === 'number' ? raw.tick : base.tick
  const rawTime = typeof raw?.timeSeconds === 'number'
    ? raw.timeSeconds
    : typeof raw?.time === 'number'
      ? raw.time
      : base.timeSeconds

  const sceneObjects = raw?.scenes?.default?.objects
  const worldEntities: WorldEntity[] = raw?.world?.entities
    ? raw.world.entities
    : sceneObjects
      ? Object.entries(sceneObjects).map(([id, value]: [string, any]) => ({
          id,
          name: value.type === 'robot' ? 'RPBOT Agent' : id,
          type: value.type || 'object',
          position: (value.position || [0, 0, 0]) as Vector3,
          velocity: (value.velocity || [0, 0, 0]) as Vector3,
        }))
      : base.world.entities

  const robotFromScene = worldEntities.find((entity) => entity.id === 'robot')
  const defaultAction = base.agent.currentAction

  const agent: AgentSnapshot = {
    id: raw?.agent?.id || robotFromScene?.id || base.agent.id,
    name: raw?.agent?.name || base.agent.name,
    position: (raw?.agent?.position || robotFromScene?.position || base.agent.position) as Vector3,
    orientation: typeof raw?.agent?.orientation === 'number' ? raw.agent.orientation : base.agent.orientation,
    currentAction: (raw?.plan?.actionState || raw?.agent?.currentAction || defaultAction) as SimActionState,
    targetEntityId: raw?.agent?.targetEntityId || base.agent.targetEntityId,
  }

  const nearby: WorldEntity[] = raw?.perceivedNearby
    || raw?.perception?.nearby_objects?.map((obj: any) => ({
      id: obj.id,
      name: obj.name || obj.id,
      type: obj.type || 'object',
      position: (obj.position || [0, 0, 0]) as Vector3,
      distance: typeof obj.distance === 'number' ? obj.distance : undefined,
      status: obj.status,
    }))
    || base.perceivedNearby

  const emotions: EmotionState[] = raw?.emotions || base.emotions
  const physicalCondition: PhysicalCondition = raw?.physicalCondition || base.physicalCondition
  const goal: GoalState = raw?.goal || base.goal

  const plan: PlanState = raw?.plan
    ? {
        steps: raw.plan.steps || base.plan.steps,
        currentStepIndex: typeof raw.plan.currentStepIndex === 'number' ? raw.plan.currentStepIndex : base.plan.currentStepIndex,
        currentAction: raw.plan.currentAction || base.plan.currentAction,
      }
    : base.plan

  const recentMemoryUpdates: MemoryUpdate[] = raw?.recentMemoryUpdates || raw?.memoryUpdates || base.recentMemoryUpdates
  const interactionHistory: InteractionEvent[] = raw?.interactionHistory || base.interactionHistory
  const chatMessages: GroundedChatMessage[] = raw?.chatMessages || base.chatMessages

  return {
    tick: rawTick,
    timeSeconds: rawTime,
    paused: typeof raw?.paused === 'boolean' ? raw.paused : base.paused,
    world: {
      sceneId: rawScene,
      entities: worldEntities,
    },
    agent,
    perceivedNearby: nearby,
    emotions,
    physicalCondition,
    goal,
    plan,
    recentMemoryUpdates,
    interactionHistory,
    chatMessages,
  }
}

const fallbackTickAdvance = (snapshot: SimulationSnapshot, steps: number): SimulationSnapshot => {
  const next = { ...snapshot }

  for (let i = 0; i < steps; i += 1) {
    const tick = next.tick + 1
    const actionCycle: SimActionState[] = ['orient', 'walk', 'interact', 'idle']
    const nextAction = actionCycle[tick % actionCycle.length]
    const target = next.perceivedNearby[tick % Math.max(next.perceivedNearby.length, 1)]

    const movedPosition: Vector3 = [...next.agent.position] as Vector3
    if (nextAction === 'walk' && target) {
      const dx = target.position[0] - movedPosition[0]
      const dz = target.position[2] - movedPosition[2]
      movedPosition[0] = movedPosition[0] + dx * 0.22
      movedPosition[2] = movedPosition[2] + dz * 0.22
    }

    next.tick = tick
    next.timeSeconds = next.timeSeconds + 1
    next.agent = {
      ...next.agent,
      position: movedPosition,
      currentAction: nextAction,
      targetEntityId: target?.id,
      orientation: Math.atan2((target?.position[0] || 0) - movedPosition[0], (target?.position[2] || 1) - movedPosition[2]),
    }

    next.plan = {
      ...next.plan,
      currentStepIndex: tick % Math.max(next.plan.steps.length, 1),
      currentAction:
        nextAction === 'walk'
          ? `Walking toward ${target?.name || 'target'}`
          : nextAction === 'interact'
            ? `Interacting with ${target?.name || 'target'}`
            : nextAction === 'orient'
              ? `Orienting toward ${target?.name || 'target'}`
              : 'Waiting for next instruction',
    }

    next.emotions = next.emotions.map((emotion) => {
      const jitter = (Math.random() - 0.5) * 0.08
      return { ...emotion, intensity: clamp(emotion.intensity + jitter, 0, 1) }
    })

    next.physicalCondition = {
      ...next.physicalCondition,
      energy: clamp(next.physicalCondition.energy - 0.02, 0, 1),
      stamina: clamp(next.physicalCondition.stamina - 0.015, 0, 1),
      stress: clamp(next.physicalCondition.stress + (nextAction === 'interact' ? 0.03 : -0.01), 0, 1),
    }

    next.recentMemoryUpdates = [
      {
        id: makeId(),
        tick,
        timestamp: nowIso(),
        type: nextAction === 'interact' ? 'interaction' : 'observation',
        content: `Tick ${tick}: ${next.plan.currentAction}. Nearby count ${next.perceivedNearby.length}.`,
      },
      ...next.recentMemoryUpdates,
    ].slice(0, 20)
  }

  return next
}

const groundedReply = (snapshot: SimulationSnapshot, message: string): GroundedChatMessage => {
  const visible = snapshot.perceivedNearby.slice(0, 3).map((entity) => entity.name).join(', ') || 'no major objects'

  return {
    id: makeId(),
    role: 'agent',
    tick: snapshot.tick,
    timestamp: nowIso(),
    content: `Acknowledged: "${message}". I am ${snapshot.plan.currentAction.toLowerCase()} and currently see ${visible}.`,
    grounding: `Tick ${snapshot.tick} • Goal: ${snapshot.goal.text}`,
  }
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
      const raw = await requestJson('/simulation/state')
      const snapshot = fromBackend(raw)
      set({
        snapshot,
        loading: false,
        agentPath: [snapshot.agent.position],
      })
    } catch {
      const fallback = createFallbackSnapshot()
      set({
        snapshot: fallback,
        loading: false,
        agentPath: [fallback.agent.position],
        error: 'Backend unavailable, using local simulation fallback.',
      })
    }
  },

  advanceTicks: async (steps = 1) => {
    const current = get().snapshot
    if (!current) return

    set({ isAdvancing: true, error: null })

    try {
      const raw = await requestJson('/simulation/tick', {
        method: 'POST',
        body: JSON.stringify({ steps }),
      })

      const snapshot = fromBackend(raw, current)
      set((state) => ({
        snapshot,
        isAdvancing: false,
        agentPath: [...state.agentPath, snapshot.agent.position].slice(-64),
      }))
    } catch {
      const snapshot = fallbackTickAdvance(current, steps)
      set((state) => ({
        snapshot,
        isAdvancing: false,
        error: 'Using local tick fallback. Connect backend to sync authoritative state.',
        agentPath: [...state.agentPath, snapshot.agent.position].slice(-64),
      }))
    }
  },

  sendGroundedChat: async (message: string) => {
    const trimmed = message.trim()
    const snapshot = get().snapshot
    if (!snapshot || !trimmed) return

    const userMessage: GroundedChatMessage = {
      id: makeId(),
      role: 'user',
      tick: snapshot.tick,
      timestamp: nowIso(),
      content: trimmed,
      grounding: `User instruction grounded to tick ${snapshot.tick}`,
    }

    set((state) => ({
      isSendingChat: true,
      snapshot: state.snapshot
        ? { ...state.snapshot, chatMessages: [...state.snapshot.chatMessages, userMessage] }
        : state.snapshot,
    }))

    try {
      const raw = await requestJson('/simulation/chat', {
        method: 'POST',
        body: JSON.stringify({ message: trimmed, grounded: true }),
      })

      const backendSnapshot = fromBackend(raw, get().snapshot || snapshot)
      set({ snapshot: backendSnapshot, isSendingChat: false })
    } catch {
      const latest = get().snapshot
      if (!latest) {
        set({ isSendingChat: false })
        return
      }

      const reply = groundedReply(latest, trimmed)
      const memory: MemoryUpdate = {
        id: makeId(),
        tick: latest.tick,
        timestamp: nowIso(),
        type: 'interaction',
        content: `User asked: "${trimmed}". Agent produced grounded fallback reply.`,
      }

      set({
        isSendingChat: false,
        error: 'Chat endpoint unavailable. Added locally grounded response.',
        snapshot: {
          ...latest,
          chatMessages: [...latest.chatMessages, reply],
          recentMemoryUpdates: [memory, ...latest.recentMemoryUpdates].slice(0, 20),
          interactionHistory: [
            {
              id: makeId(),
              tick: latest.tick,
              timestamp: nowIso(),
              with: 'operator',
              summary: `Grounded chat fallback for message: ${trimmed}`,
            },
            ...latest.interactionHistory,
          ].slice(0, 20),
        },
      })
    }
  },

  togglePause: async () => {
    const snapshot = get().snapshot
    if (!snapshot) return
    const paused = !snapshot.paused

    try {
      // await requestJson('/simulation/pause', {
        method: 'POST',
        body: JSON.stringify({ paused }),
      })
      set((state) => (state.snapshot ? { snapshot: { ...state.snapshot, paused } } : state))
    } catch {
      set((state) => ({
        error: 'Pause state updated locally only (backend pause endpoint unavailable).',
        snapshot: state.snapshot ? { ...state.snapshot, paused } : state.snapshot,
      }))
    }
  },

  selectEntity: (entityId) => set({ selectedEntityId: entityId }),
}))
