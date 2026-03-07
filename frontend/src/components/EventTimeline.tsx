'use client'

import React from 'react'
import { SimulationSnapshot } from '../store/useSimulationStore'

type EventTimelineProps = {
  snapshot: SimulationSnapshot | null
}

type TimelineItem = {
  id: string
  tick: number
  timestamp: string
  kind: 'action' | 'thought' | 'memory' | 'event'
  content: string
}

const kindTone: Record<TimelineItem['kind'], string> = {
  action: 'border-blue-200 bg-blue-50 text-blue-800',
  thought: 'border-violet-200 bg-violet-50 text-violet-800',
  memory: 'border-slate-200 bg-slate-50 text-slate-800',
  event: 'border-amber-200 bg-amber-50 text-amber-800',
}

const toTimelineItems = (snapshot: SimulationSnapshot): TimelineItem[] => {
  const memoryItems: TimelineItem[] = snapshot.recentMemoryUpdates.map((item) => ({
    id: `mem-${item.id}`,
    tick: item.tick,
    timestamp: item.timestamp,
    kind: item.type === 'decision' || item.type === 'reflection' ? 'thought' : 'memory',
    content: item.content,
  }))

  const interactionItems: TimelineItem[] = snapshot.interactionHistory.map((item) => ({
    id: `evt-${item.id}`,
    tick: item.tick,
    timestamp: item.timestamp,
    kind: 'event',
    content: `${item.with}: ${item.summary}`,
  }))

  const actionStateItem: TimelineItem = {
    id: `action-state-${snapshot.tick}`,
    tick: snapshot.tick,
    timestamp: new Date().toISOString(),
    kind: 'action',
    content: `${snapshot.plan.currentAction || snapshot.agent.currentAction} • goal: ${snapshot.goal.text}`,
  }

  return [...memoryItems, ...interactionItems, actionStateItem]
    .sort((a, b) => {
      if (a.tick !== b.tick) return b.tick - a.tick
      if (a.timestamp === b.timestamp) return 0
      return a.timestamp < b.timestamp ? 1 : -1
    })
    .slice(0, 24)
}

const EventTimeline: React.FC<EventTimelineProps> = ({ snapshot }) => {
  if (!snapshot) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-500">
        No timeline data available.
      </section>
    )
  }

  const items = toTimelineItems(snapshot)

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="mb-2">
        <p className="text-xs uppercase tracking-wide text-slate-500">Timeline</p>
        <p className="text-sm text-slate-700">Action / thought / memory / event stream</p>
      </div>

      <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
        {items.map((item) => (
          <div key={item.id} className="rounded-lg border border-slate-200 bg-white p-2">
            <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
              <span className={`rounded px-1.5 py-0.5 font-semibold uppercase tracking-wide ${kindTone[item.kind]}`}>
                {item.kind}
              </span>
              <span>tick {item.tick}</span>
            </div>
            <p className="text-sm text-slate-900">{item.content}</p>
          </div>
        ))}

        {items.length === 0 ? <p className="text-sm text-slate-500">No events recorded yet.</p> : null}
      </div>
    </section>
  )
}

export default EventTimeline
