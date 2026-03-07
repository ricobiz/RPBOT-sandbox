'use client'

import React from 'react'
import { useSimulationStore } from '../store/useSimulationStore'

const EventTimeline: React.FC = () => {
  const snapshot = useSimulationStore((state) => state.snapshot)

  if (!snapshot) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-500">
        No memory timeline available.
      </section>
    )
  }

  const timelineItems = [
    ...snapshot.recentMemoryUpdates.map((item) => ({
      id: item.id,
      label: item.type,
      tick: item.tick,
      timestamp: item.timestamp,
      content: item.content,
    })),
    ...snapshot.interactionHistory.map((item) => ({
      id: item.id,
      label: 'interaction',
      tick: item.tick,
      timestamp: item.timestamp,
      content: `${item.with}: ${item.summary}`,
    })),
  ]
    .sort((a, b) => (a.tick === b.tick ? (a.timestamp < b.timestamp ? 1 : -1) : b.tick - a.tick))
    .slice(0, 20)

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="mb-2">
        <p className="text-xs uppercase tracking-wide text-slate-500">Memory / events</p>
        <p className="text-sm text-slate-700">What the agent remembers and recent interactions</p>
      </div>
      <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
        {timelineItems.length === 0 ? (
          <p className="text-sm text-slate-500">No recent events yet.</p>
        ) : null}
        {timelineItems.map((item) => (
          <div key={item.id} className="rounded-lg border border-slate-200 bg-slate-50 p-2">
            <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
              <span className="uppercase tracking-wide">{item.label}</span>
              <span>tick {item.tick}</span>
            </div>
            <p className="text-xs text-slate-500">{new Date(item.timestamp).toLocaleTimeString()}</p>
            <p className="text-sm text-slate-800">{item.content}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

export default EventTimeline
