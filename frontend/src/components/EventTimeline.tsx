import React from 'react'
import { useSimulationStore } from '../store/useSimulationStore'
import { Brain, Eye, AlertTriangle, CheckCircle, Activity } from 'lucide-react'

const iconMap = {
  thought: Brain,
  observation: Eye,
  decision: Activity,
  obstacle: AlertTriangle,
  result: CheckCircle,
}

const EventTimeline: React.FC = () => {
  const events = useSimulationStore((state) => state.events)

  return (
    <div style={{
      maxHeight: '400px',
      overflowY: 'auto',
      padding: '8px',
      background: '#fafafa',
      border: '1px solid #ddd',
      borderRadius: '4px',
      fontFamily: 'sans-serif',
      fontSize: '14px',
    }}>
      {events.map((e) => {
        const Icon = iconMap[e.type] || Activity
        const date = new Date(e.timestamp)
        const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        return (
          <div key={e.id} style={{ display: 'flex', marginBottom: '8px' }}>
            <Icon size={20} style={{ marginRight: '8px', color: '#555' }} />
            <div>
              <div style={{ fontWeight: 'bold' }}>{timeStr}</div>
              <div>{e.content}</div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default EventTimeline