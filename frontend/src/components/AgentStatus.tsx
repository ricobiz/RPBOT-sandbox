'use client'

import React from 'react'
import { SimulationSnapshot } from '../store/useSimulationStore'

type AgentStatusProps = {
  snapshot: SimulationSnapshot | null
  selectedEntityId?: string | null
  onSelectEntity?: (entityId: string | null) => void
}

const meterColor = (value: number) => {
  if (value > 0.7) return 'bg-emerald-500'
  if (value > 0.4) return 'bg-amber-500'
  return 'bg-rose-500'
}

const StatMeter: React.FC<{ label: string; value: number }> = ({ label, value }) => {
  const pct = Math.round(value * 100)
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs text-slate-600">
        <span>{label}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 w-full rounded bg-slate-200">
        <div className={`h-2 rounded ${meterColor(value)}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

const AgentStatus: React.FC<AgentStatusProps> = ({ snapshot, selectedEntityId, onSelectEntity }) => {
  if (!snapshot) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-500">
        Agent status unavailable.
      </section>
    )
  }

  const topEmotion = [...snapshot.emotions].sort((a, b) => b.intensity - a.intensity).slice(0, 3)
  const currentStep = snapshot.plan.steps[snapshot.plan.currentStepIndex] || 'No active step'
  const targetEntity = snapshot.world.entities.find((entity) => entity.id === snapshot.agent.targetEntityId)

  return (
    <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div>
        <p className="text-xs uppercase tracking-wide text-slate-500">Agent status</p>
        <p className="text-sm font-semibold text-slate-900">{snapshot.agent.name}</p>
      </div>

      <div className="space-y-1 text-sm text-slate-800">
        <p><span className="font-semibold">Emotional state:</span> {topEmotion.map((emotion) => `${emotion.name} ${Math.round(emotion.intensity * 100)}%`).join(' • ') || 'Unknown'}</p>
        <p><span className="font-semibold">Current goal:</span> {snapshot.goal.text}</p>
        <p><span className="font-semibold">Plan summary:</span> Step {snapshot.plan.currentStepIndex + 1}/{Math.max(snapshot.plan.steps.length, 1)} — {currentStep}</p>
        <p><span className="font-semibold">Current action:</span> {snapshot.plan.currentAction || snapshot.agent.currentAction}</p>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <StatMeter label="Energy" value={snapshot.physicalCondition.energy} />
        <StatMeter label="Stamina" value={snapshot.physicalCondition.stamina} />
        <StatMeter label="Stress" value={1 - snapshot.physicalCondition.stress} />
        <StatMeter label="Health" value={snapshot.physicalCondition.health} />
      </div>

      <div className="rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700">
        <p><span className="font-semibold">World facts:</span> scene {snapshot.world.sceneId} • entities {snapshot.world.entities.length}</p>
        <p><span className="font-semibold">Focus target:</span> {targetEntity?.name || 'None selected'}</p>
        <p><span className="font-semibold">Nearby perceived:</span> {snapshot.perceivedNearby.length}</p>
      </div>

      <div>
        <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Key perceptions</p>
        <div className="space-y-2">
          {snapshot.perceivedNearby.slice(0, 4).map((entity) => (
            <button
              key={entity.id}
              onClick={() => onSelectEntity?.(entity.id)}
              className={`w-full rounded-lg border p-2 text-left text-sm ${selectedEntityId === entity.id ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-white'}`}
            >
              <p className="font-semibold text-slate-900">{entity.name}</p>
              <p className="text-xs text-slate-600">
                {entity.type} • distance {entity.distance?.toFixed(2) ?? 'n/a'} • {entity.status || 'observed'}
              </p>
            </button>
          ))}
          {snapshot.perceivedNearby.length === 0 ? <p className="text-sm text-slate-500">No nearby entities currently perceived.</p> : null}
        </div>
      </div>
    </section>
  )
}

export default AgentStatus
