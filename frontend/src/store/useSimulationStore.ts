import create from 'zustand'

export type AgentState = {
  name: string
  goal: string
  action: string
  emotionalState: Record<string, number>
  physicalState: {
    energy: number
    hunger: number
  }
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
  agents: AgentState[]
  events: EventLog[]
  worldObjects: WorldObject[]
  setAgentState: (name: string, partial: Partial<AgentState>) => void
  addAgent: (agent: AgentState) => void
  removeAgent: (name: string) => void
  addEvent: (event: Omit<EventLog, 'id' | 'timestamp'>) => void
  setWorldObjects: (objects: WorldObject[]) => void
}

export const useSimulationStore = create<SimulationState>((set) => ({
  agents: [
    {
      name: 'Agent',
      goal: 'Unknown',
      action: 'Idle',
      emotionalState: {},
      physicalState: { energy: 100, hunger: 0 },
      isThinking: false,
      isMoving: false,
    },
  ],
  events: [],
  worldObjects: [],
  setAgentState: (name, partial) =>
    set((state) => ({
      agents: state.agents.map((agent) =>
        agent.name === name ? { ...agent, ...partial } : agent
      ),
    })),
  addAgent: (agent) =>
    set((state) => ({ agents: [...state.agents, agent] })),
  removeAgent: (name) =>
    set((state) => ({ agents: state.agents.filter((agent) => agent.name !== name) })),
  addEvent: (event) =>
    set((state) => ({
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