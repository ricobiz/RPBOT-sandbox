'use client'

import React from 'react'
import { useSimulationStore } from '../store/useSimulationStore'

const meterColor = (value: number) => {
  if (value > 0.7) return 'bg-emerald-500'
  if (value > 0.4) return 'bg-amber-500'
  return 'bg-rose-500'
}

const normalize01 = (value: number) => {
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(1, value))
}

const StatMeter: React.FC<{ label: string; value: number }> = ({ label, value }) => {
  const normalized = normalize01(value)
  const pct = Math.round(normalized * 100)
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs text-slate-600">
        <span>{label}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 w-full rounded bg-slate-200">
        <div className={`h-2 rounded ${meterColor(normalized)}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

const AgentStatus: React.FC = () => {
  const snapshot = useSimulationStore((state) => state.snapshot)

  if (!snapshot) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-500">
        Agent status unavailable.
      </section>
    )
  }

  const topEmotion = [...snapshot.emotions].sort((a, b) => b.intensity - a.intensity).slice(0, 3)
  const visibleEntityText = snapshot.perceivedNearby.length
    ? snapshot.perceivedNearby.slice(0, 3).map((entity) => entity.name).join(', ')
    : 'No nearby entities currently perceived'

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="mb-2">
        <p className="text-xs uppercase tracking-wide text-slate-500">Agent status</p>
        <p className="text-sm font-semibold text-slate-900">{snapshot.agent.name}</p>
      </div>

      <div className="space-y-2 text-sm text-slate-800">
        <p><span className="font-semibold">Doing:</span> {snapshot.plan.currentAction}</p>
        <p><span className="font-semibold">Goal:</span> {snapshot.goal.text}</p>
        <p><span className="font-semibold">Sees:</span> {visibleEntityText}</p>
        <p>
          <span className="font-semibold">Feels:</span>{' '}
          {topEmotion.map((emotion) => `${emotion.name} ${Math.round(emotion.intensity * 100)}%`).join(' • ')}
        </p>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <StatMeter label="Energy" value={snapshot.physicalCondition.energy} />
        <StatMeter label="Stamina" value={snapshot.physicalCondition.stamina} />
        <StatMeter label="Stress" value={1 - snapshot.physicalCondition.stress} />
        <StatMeter label="Health" value={snapshot.physicalCondition.health} />
      </div>
    </section>
  )
}

export default AgentStatus
