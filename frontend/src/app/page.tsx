'use client'

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Line } from '@react-three/drei'
import { SimActionState, useSimulationStore } from '../store/useSimulationStore'

type AvatarProps = {
  position: [number, number, number]
  action: SimActionState
  orientation: number
}

const actionColor: Record<SimActionState, string> = {
  idle: '#64748b',
  walk: '#22c55e',
  interact: '#f59e0b',
  orient: '#3b82f6',
}

const pct = (value: number) => `${Math.round(value * 100)}%`

const HumanoidAvatarProxy: React.FC<AvatarProps> = ({ position, action, orientation }) => {
  const groupRef = useRef<any>(null)

  useFrame(({ clock }) => {
    if (!groupRef.current) return
    const t = clock.getElapsedTime()
    const bob = action === 'walk' ? Math.sin(t * 8) * 0.04 : action === 'interact' ? Math.sin(t * 4) * 0.02 : 0
    groupRef.current.position.set(position[0], 0.55 + bob, position[2])
    groupRef.current.rotation.y = orientation
  })

  return (
    <group ref={groupRef}>
      <mesh position={[0, 0.6, 0]}>
        <capsuleGeometry args={[0.16, 0.48, 6, 12]} />
        <meshStandardMaterial color={actionColor[action]} />
      </mesh>
      <mesh position={[0, 1.1, 0]}>
        <sphereGeometry args={[0.12, 16, 16]} />
        <meshStandardMaterial color="#e2e8f0" />
      </mesh>
    </group>
  )
}

const Viewport3D: React.FC = () => {
  const snapshot = useSimulationStore((state) => state.snapshot)
  const agentPath = useSimulationStore((state) => state.agentPath)
  const selectedEntityId = useSimulationStore((state) => state.selectedEntityId)

  const targetEntity = useMemo(
    () => snapshot?.world.entities.find((entity) => entity.id === snapshot.agent.targetEntityId),
    [snapshot],
  )

  if (!snapshot) {
    return (
      <div className="flex h-56 items-center justify-center rounded-xl border border-slate-300 bg-slate-100 text-sm text-slate-500">
        Waiting for simulation scene...
      </div>
    )
  }

  const pathPoints = agentPath.map((p) => [p[0], 0.05, p[2]] as [number, number, number])

  return (
    <div className="h-56 overflow-hidden rounded-xl border border-slate-200 bg-slate-950">
      <Canvas camera={{ position: [0, 6, 7], fov: 48 }}>
        <ambientLight intensity={0.8} />
        <directionalLight intensity={1.1} position={[5, 7, 3]} />

        <mesh rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[24, 24]} />
          <meshStandardMaterial color="#0f172a" />
        </mesh>

        {snapshot.world.entities
          .filter((entity) => entity.id !== snapshot.agent.id)
          .map((entity) => {
            const selected = selectedEntityId === entity.id
            return (
              <group key={entity.id} position={[entity.position[0], 0, entity.position[2]]}>
                <mesh position={[0, 0.35, 0]}>
                  <boxGeometry args={[0.45, 0.7, 0.45]} />
                  <meshStandardMaterial color={selected ? '#f43f5e' : '#38bdf8'} />
                </mesh>
              </group>
            )
          })}

        <HumanoidAvatarProxy
          position={snapshot.agent.position}
          action={snapshot.agent.currentAction}
          orientation={snapshot.agent.orientation}
        />

        {pathPoints.length > 1 ? <Line points={pathPoints} color="#f8fafc" lineWidth={1.5} /> : null}

        {targetEntity ? (
          <mesh position={[targetEntity.position[0], 0.02, targetEntity.position[2]]} rotation={[-Math.PI / 2, 0, 0]}>
            <ringGeometry args={[0.22, 0.3, 32]} />
            <meshBasicMaterial color="#f59e0b" />
          </mesh>
        ) : null}
      </Canvas>
    </div>
  )
}

const HomePage: React.FC = () => {
  const [chatInput, setChatInput] = useState('')

  const snapshot = useSimulationStore((state) => state.snapshot)
  const loading = useSimulationStore((state) => state.loading)
  const error = useSimulationStore((state) => state.error)
  const isAdvancing = useSimulationStore((state) => state.isAdvancing)
  const isSendingChat = useSimulationStore((state) => state.isSendingChat)
  const selectedEntityId = useSimulationStore((state) => state.selectedEntityId)

  const loadInitialState = useSimulationStore((state) => state.loadInitialState)
  const advanceTicks = useSimulationStore((state) => state.advanceTicks)
  const sendGroundedChat = useSimulationStore((state) => state.sendGroundedChat)
  const togglePause = useSimulationStore((state) => state.togglePause)
  const selectEntity = useSimulationStore((state) => state.selectEntity)

  useEffect(() => {
    loadInitialState()
  }, [loadInitialState])

  const selectedEntity = snapshot?.world.entities.find((entity) => entity.id === selectedEntityId) || null

  const timelineItems = useMemo(() => {
    if (!snapshot) return []

    return [
      ...snapshot.recentMemoryUpdates.map((item) => ({
        id: item.id,
        tick: item.tick,
        timestamp: item.timestamp,
        label: item.type,
        content: item.content,
      })),
      ...snapshot.interactionHistory.map((item) => ({
        id: item.id,
        tick: item.tick,
        timestamp: item.timestamp,
        label: 'interaction',
        content: `${item.with}: ${item.summary}`,
      })),
    ]
      .sort((a, b) => (a.tick === b.tick ? (a.timestamp < b.timestamp ? 1 : -1) : b.tick - a.tick))
      .slice(0, 30)
  }, [snapshot])

  const onSend = async () => {
    const text = chatInput.trim()
    if (!text) return
    await sendGroundedChat(text)
    setChatInput('')
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col gap-3 bg-slate-100 px-3 pb-4 pt-3 text-slate-900">
      <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="text-sm font-semibold">{snapshot?.agent.name || 'Simulation'}</p>
          <p className="text-xs text-slate-600">scene {snapshot?.world.sceneId || '-'}</p>
        </div>
        <div className="text-xs text-slate-600">
          {loading
            ? 'loading simulation...'
            : `tick ${snapshot?.tick ?? '-'} • t=${snapshot?.timeSeconds ?? '-'}s • ${snapshot?.paused ? 'paused' : 'running'}`}
        </div>
        {error ? (
          <div className="mt-2 flex items-center justify-between gap-2 rounded border border-amber-200 bg-amber-50 p-2">
            <p className="text-xs text-amber-800">{error}</p>
            <button
              type="button"
              onClick={loadInitialState}
              className="rounded bg-amber-600 px-2 py-1 text-xs font-semibold text-white"
            >
              Retry
            </button>
          </div>
        ) : null}
      </section>

      <Viewport3D />

      <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-xs uppercase tracking-wide text-slate-500">State</p>
          <p className="text-xs text-slate-500">action {snapshot?.agent.currentAction || '-'}</p>
        </div>
        <div className="space-y-1 text-sm">
          <p>
            <span className="font-semibold">goal</span> {snapshot?.goal.text || '-'}
          </p>
          <p>
            <span className="font-semibold">priority</span> {snapshot?.goal.priority || '-'}
          </p>
          <p>
            <span className="font-semibold">plan</span> {snapshot?.plan.currentAction || '-'}
          </p>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div className="rounded border border-slate-200 bg-slate-50 p-2">energy {pct(snapshot?.physicalCondition.energy || 0)}</div>
          <div className="rounded border border-slate-200 bg-slate-50 p-2">stamina {pct(snapshot?.physicalCondition.stamina || 0)}</div>
          <div className="rounded border border-slate-200 bg-slate-50 p-2">stress {pct(snapshot?.physicalCondition.stress || 0)}</div>
          <div className="rounded border border-slate-200 bg-slate-50 p-2">health {pct(snapshot?.physicalCondition.health || 0)}</div>
        </div>
        <div className="mt-2 flex flex-wrap gap-1">
          {(snapshot?.emotions || []).map((emotion) => (
            <span key={emotion.name} className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs">
              {emotion.name} {pct(emotion.intensity)}
            </span>
          ))}
          {snapshot && snapshot.emotions.length === 0 ? <span className="text-xs text-slate-500">no emotion data</span> : null}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Observability</p>
        <div className="space-y-2">
          {(snapshot?.perceivedNearby || []).map((entity) => (
            <button
              key={entity.id}
              type="button"
              onClick={() => selectEntity(entity.id)}
              className={`w-full rounded-lg border p-2 text-left text-sm ${selectedEntityId === entity.id ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-slate-50'}`}
            >
              <p className="font-semibold">{entity.name}</p>
              <p className="text-xs text-slate-600">
                {entity.type} • d={entity.distance?.toFixed(2) ?? 'n/a'} • {entity.status || 'observed'}
              </p>
            </button>
          ))}
          {!loading && snapshot?.perceivedNearby.length === 0 ? (
            <p className="text-sm text-slate-500">no perceived entities</p>
          ) : null}
        </div>
        {selectedEntity ? (
          <div className="mt-2 rounded border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700">
            selected {selectedEntity.name} @ [{selectedEntity.position.map((n) => n.toFixed(2)).join(', ')}]
          </div>
        ) : null}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Timeline</p>
        <div className="max-h-48 space-y-2 overflow-y-auto pr-1">
          {timelineItems.map((item) => (
            <div key={item.id} className="rounded border border-slate-200 bg-slate-50 p-2 text-sm">
              <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
                <span>{item.label}</span>
                <span>tick {item.tick}</span>
              </div>
              <p>{item.content}</p>
            </div>
          ))}
          {timelineItems.length === 0 ? <p className="text-sm text-slate-500">no timeline events</p> : null}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Chat</p>
        <div className="mb-3 max-h-44 space-y-2 overflow-y-auto pr-1">
          {(snapshot?.chatMessages || []).map((message) => (
            <div key={message.id} className={`rounded-lg p-2 text-sm ${message.role === 'user' ? 'bg-blue-50' : message.role === 'agent' ? 'bg-emerald-50' : 'bg-slate-100'}`}>
              <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
                <span>{message.role}</span>
                <span>tick {message.tick}</span>
              </div>
              <p>{message.content}</p>
            </div>
          ))}
          {snapshot?.chatMessages.length === 0 ? <p className="text-sm text-slate-500">no chat messages</p> : null}
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={chatInput}
            onChange={(event) => setChatInput(event.target.value)}
            placeholder="Send grounded message"
            className="h-10 flex-1 rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-slate-500"
            onKeyDown={(event) => {
              if (event.key === 'Enter') onSend()
            }}
          />
          <button
            type="button"
            onClick={onSend}
            disabled={!snapshot || isSendingChat || !chatInput.trim()}
            className="h-10 rounded-lg bg-blue-600 px-3 text-sm font-semibold text-white disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </section>

      <section className="sticky bottom-0 z-20 rounded-xl border border-slate-200 bg-white/95 p-3 shadow-sm backdrop-blur">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => advanceTicks(1)}
            disabled={!snapshot || snapshot.paused || isAdvancing || loading}
            className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-40"
          >
            +1 Tick
          </button>
          <button
            type="button"
            onClick={() => advanceTicks(5)}
            disabled={!snapshot || snapshot.paused || isAdvancing || loading}
            className="rounded-lg bg-slate-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-40"
          >
            +5 Ticks
          </button>
          <button
            type="button"
            onClick={togglePause}
            disabled={!snapshot}
            className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-800 disabled:opacity-40"
          >
            {snapshot?.paused ? 'Resume' : 'Pause'}
          </button>
        </div>
      </section>
    </main>
  )
}

export default HomePage
