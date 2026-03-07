'use client'

import React, { useState } from 'react'
import { SimulationSnapshot } from '../store/useSimulationStore'

type BottomControlsProps = {
  snapshot: SimulationSnapshot | null
  isAdvancing: boolean
  isSendingChat: boolean
  onAdvanceTicks: (steps?: number) => Promise<void>
  onTogglePause: () => Promise<void>
  onSendGroundedChat: (message: string) => Promise<void>
}

const BottomControls: React.FC<BottomControlsProps> = ({
  snapshot,
  isAdvancing,
  isSendingChat,
  onAdvanceTicks,
  onTogglePause,
  onSendGroundedChat,
}) => {
  const [message, setMessage] = useState('')

  const onSend = async () => {
    if (!message.trim()) return
    await onSendGroundedChat(message)
    setMessage('')
  }

  const disabled = !snapshot

  return (
    <section className="space-y-2 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex items-center justify-between rounded-lg bg-slate-50 px-2 py-1.5 text-xs text-slate-700">
        <span className="font-medium">Action state</span>
        <span>
          {snapshot ? `${snapshot.paused ? 'Paused' : 'Running'} • ${snapshot.agent.currentAction}` : 'No snapshot'}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <button
          onClick={() => onAdvanceTicks(1)}
          disabled={isAdvancing || disabled || !!snapshot?.paused}
          className="rounded-lg bg-slate-900 px-2 py-2 text-xs font-semibold text-white disabled:opacity-40"
        >
          +1 Tick
        </button>
        <button
          onClick={() => onAdvanceTicks(5)}
          disabled={isAdvancing || disabled || !!snapshot?.paused}
          className="rounded-lg bg-slate-700 px-2 py-2 text-xs font-semibold text-white disabled:opacity-40"
        >
          +5 Ticks
        </button>
        <button
          onClick={onTogglePause}
          disabled={disabled}
          className="rounded-lg border border-slate-300 px-2 py-2 text-xs font-semibold text-slate-800 disabled:opacity-40"
        >
          {snapshot?.paused ? 'Resume' : 'Pause'}
        </button>
      </div>

      <div className="space-y-2 rounded-lg border border-slate-200 p-2">
        <p className="text-xs uppercase tracking-wide text-slate-500">Grounded chat</p>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Ask based on current scene, memory, and goal"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="h-10 flex-1 rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-slate-500"
          />
          <button
            onClick={onSend}
            disabled={isSendingChat || disabled || !message.trim()}
            className="h-10 rounded-lg bg-blue-600 px-3 text-sm font-semibold text-white disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </div>

      <div className="max-h-36 space-y-1 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-2">
        {(snapshot?.chatMessages || []).slice(-4).reverse().map((msg) => (
          <div key={msg.id} className="text-xs text-slate-700">
            <p className="font-semibold uppercase tracking-wide text-slate-500">
              {msg.role} • tick {msg.tick}
            </p>
            <p className="text-slate-900">{msg.content}</p>
          </div>
        ))}
        {snapshot?.chatMessages.length === 0 ? <p className="text-xs text-slate-500">No grounded chat yet.</p> : null}
      </div>
    </section>
  )
}

export default BottomControls
