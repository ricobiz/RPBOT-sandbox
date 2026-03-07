import React from 'react'
import { useSimulationStore } from '../store/useSimulationStore'
import { Activity, Brain, ArrowRight, Clock } from 'lucide-react'

const AgentStatus: React.FC = () => {
  const agent = useSimulationStore((state) => state.agent)

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      padding: '8px 12px',
      background: '#f5f5f5',
      borderRadius: '4px',
      fontFamily: 'sans-serif',
      fontSize: '14px',
    }}>
      <div style={{ marginRight: '12px', fontWeight: 'bold' }}>{agent.name}</div>
      <div style={{ marginRight: '12px' }}>
        <span style={{ marginRight: '4px' }}>Goal:</span>{agent.goal}
      </div>
      <div style={{ marginRight: '12px' }}>
        <span style={{ marginRight: '4px' }}>Action:</span>{agent.action}
      </div>
      <div style={{ marginRight: '12px' }}>
        <span style={{ marginRight: '4px' }}>Emotion:</span>{agent.emotionalState}
      </div>
      <div style={{ display: 'flex', alignItems: 'center' }}>
        {agent.isThinking && <Brain size={16} style={{ marginRight: '4px' }} />}
        {agent.isMoving && <ArrowRight size={16} style={{ marginRight: '4px' }} />}
        <Clock size={16} />
      </div>
    </div>
  )
}

export default AgentStatus