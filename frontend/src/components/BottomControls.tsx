'use client'

import React, { useState } from 'react'
import { useSimulationStore } from '../store/useSimulationStore'

const BottomControls: React.FC = () => {
  const [message, setMessage] = useState('')

  const snapshot = useSimulationStore((state) => state.snapshot)
  const advanceTicks = useSimulationStore((state) => state.advanceTicks)
  const togglePause = useSimulationStore((state) => state.togglePause)
  const sendGroundedChat = useSimulationStore((state) => state.sendGroundedChat)
  const isAdvancing = useSimulationStore((state) => state.isAdvancing)
  const isSendingChat = useSimulationStore((state) => state.isSendingChat)

  const onSend = async () => {
    if (!message.trim()) return
    await sendGroundedChat(message)
    setMessage('')
  }

  return (
    <section className="sticky bottom-0 z-20 border-t border-slate-200 bg-white/95 p-3 backdrop-blur">
      <div className="mb-2 flex items-center gap-2">
        <button
          onClick={() => advanceTicks(1)}
          disabled={isAdvancing || !snapshot || snapshot.paused}
          className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-40"
        >
          +1 Tick
        </button>
        <button
          onClick={() => advanceTicks(5)}
          disabled={isAdvancing || !snapshot || snapshot.paused}
          className="rounded-lg bg-slate-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-40"
        >
          +5 Ticks
        </button>
        <button
          onClick={togglePause}
          disabled={!snapshot}
          className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-800 disabled:opacity-40"
        >
          {snapshot?.paused ? 'Resume' : 'Pause'}
        </button>
      </div>

      <div className="flex items-center gap-2">
        <input
          type="text"
          placeholder="Send grounded chat: ask what the agent sees / should do"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          className="h-10 flex-1 rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-slate-500"
        />
        <button
          onClick={onSend}
          disabled={isSendingChat || !snapshot || !message.trim()}
          className="h-10 rounded-lg bg-blue-600 px-3 text-sm font-semibold text-white disabled:opacity-40"
        >
          Send
        </button>
      </div>
    </section>
  )
}

export default BottomControls
