'use client'

import React, { useEffect, useMemo, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Line } from '@react-three/drei'
import AgentStatus from '../components/AgentStatus'
import EventTimeline from '../components/EventTimeline'
import BottomControls from '../components/BottomControls'
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

const HumanoidAvatarProxy: React.FC<AvatarProps & { modelUrl?: string }> = ({
  position,
  action,
  orientation,
}) => {
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
      <mesh position={[0.08, 1.12, 0.1]}>
        <sphereGeometry args={[0.02, 8, 8]} />
        <meshStandardMaterial color="#0f172a" />
      </mesh>
      <mesh position={[-0.08, 1.12, 0.1]}>
        <sphereGeometry args={[0.02, 8, 8]} />
        <meshStandardMaterial color="#0f172a" />
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
    return <div className="flex h-56 items-center justify-center rounded-xl bg-slate-200 text-sm text-slate-600">Loading viewport…</div>
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
  const snapshot = useSimulationStore((state) => state.snapshot)
  const loading = useSimulationStore((state) => state.loading)
  const error = useSimulationStore((state) => state.error)
  const isAdvancing = useSimulationStore((state) => state.isAdvancing)
  const isSendingChat = useSimulationStore((state) => state.isSendingChat)
  const loadInitialState = useSimulationStore((state) => state.loadInitialState)
  const advanceTicks = useSimulationStore((state) => state.advanceTicks)
  const sendGroundedChat = useSimulationStore((state) => state.sendGroundedChat)
  const togglePause = useSimulationStore((state) => state.togglePause)
  const selectEntity = useSimulationStore((state) => state.selectEntity)
  const selectedEntityId = useSimulationStore((state) => state.selectedEntityId)

  useEffect(() => {
    loadInitialState()
  }, [loadInitialState])

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col gap-3 bg-slate-100 px-3 py-3 text-slate-900">
      <header className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <h1 className="text-base font-semibold">RPBOT Mobile Simulation Sandbox</h1>
        <p className="text-xs text-slate-600">Grounded agent state, timeline, and controls in a compact mobile layout.</p>
        <div className="mt-2 text-xs text-slate-500">
          {loading ? 'Loading simulation…' : `Tick ${snapshot?.tick ?? '-'} • t=${snapshot?.timeSeconds ?? '-'}s • ${snapshot?.paused ? 'Paused' : 'Running'}`}
        </div>
        {error ? <p className="mt-1 text-xs text-amber-700">{error}</p> : null}
      </header>

      <section className="space-y-2 rounded-xl border border-slate-200 bg-white p-2 shadow-sm">
        <p className="px-1 text-xs uppercase tracking-wide text-slate-500">Scene viewport</p>
        <Viewport3D />
      </section>

      <AgentStatus snapshot={snapshot} selectedEntityId={selectedEntityId} onSelectEntity={selectEntity} />

      <EventTimeline snapshot={snapshot} />

      <BottomControls
        snapshot={snapshot}
        isAdvancing={isAdvancing}
        isSendingChat={isSendingChat}
        onAdvanceTicks={advanceTicks}
        onTogglePause={togglePause}
        onSendGroundedChat={sendGroundedChat}
      />
    </main>
  )
}

export default HomePage
