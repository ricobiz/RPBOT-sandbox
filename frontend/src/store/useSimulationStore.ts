import create from 'zustand'

export type AgentState = {
  name: string
  goal: string
  action: string
  emotionalState: string
  isThinking: boolean
  isMoving: boolean
}

export type EventLog = {
  id: string
  type: 'thought' | 'observation' | 'decision' | 'obstacle' | 'result'
  content: string
  timestamp: number
}

export type WorldObject = {
  id: string
  type: string
  properties: Record<string, any>
}

export type SimulationState = {
  agent: AgentState
  events: EventLog[]
  worldObjects: WorldObject[]
  setAgentState: (partial: Partial<AgentState>) => void
  addEvent: (event: Omit<EventLog, 'id' | 'timestamp'>) => void
  setWorldObjects: (objects: WorldObject[]) => void
}

export const useSimulationStore = create<SimulationState>((set) => ({
  agent: {
    name: 'Agent',
    goal: 'Unknown',
    action: 'Idle',
    emotionalState: 'Neutral',
    isThinking: false,
    isMoving: false,
  },
  events: [],
  worldObjects: [],
  setAgentState: (partial) => set((state) => ({ agent: { ...state.agent, ...partial } })),
  addEvent: (event) => set((state) => ({
    events: [
      {
        id: Math.random().toString(36).substr(2, 9),
        timestamp: Date.now(),
        ...event,
      },
      ...state.events,
    ],
  })),
  setWorldObjects: (objects) => set({ worldObjects: objects }),
}))