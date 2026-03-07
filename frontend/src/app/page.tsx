'use client'

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Line } from '@react-three/drei'
import AgentStatus from '../components/AgentStatus'
import BottomControls from '../components/BottomControls'
import EventTimeline from '../components/EventTimeline'
import { type SimActionState, useSimulationStore } from '../store/useSimulationStore'

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
  const [sceneReady, setSceneReady] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined' || typeof document === 'undefined') return

    try {
      const canvas = document.createElement('canvas')
      const hasWebGl = !!(canvas.getContext('webgl') || canvas.getContext('experimental-webgl'))
      setSceneReady(hasWebGl)
    } catch {
      setSceneReady(false)
    }
  }, [])

  const targetEntity = useMemo(
    () => snapshot?.world.entities.find((entity) => entity.id === snapshot.agent.targetEntityId),
    [snapshot],
  )

  if (!snapshot) {
    return (
      <div className="flex h-56 items-center justify-center rounded-xl border border-slate-300 bg-slate-100 text-sm text-slate-500">
        No scene data
      </div>
    )
  }

  if (!sceneReady) {
    return (
      <div className="flex h-56 items-center justify-center rounded-xl border border-slate-300 bg-slate-100 text-sm text-slate-500">
        3D preview unavailable on this device.
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
  const snapshot = useSimulationStore((state) => state.snapshot)
  const loading = useSimulationStore((state) => state.loading)
  const error = useSimulationStore((state) => state.error)
  const selectedEntityId = useSimulationStore((state) => state.selectedEntityId)
  const selectEntity = useSimulationStore((state) => state.selectEntity)
  const loadInitialState = useSimulationStore((state) => state.loadInitialState)

  useEffect(() => {
    loadInitialState()
  }, [loadInitialState])

  const selectedEntity = snapshot?.world.entities.find((entity) => entity.id === selectedEntityId) || null

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col gap-3 bg-slate-100 px-3 pb-4 pt-3 text-slate-900">
      <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="text-sm font-semibold">{snapshot?.agent.name || 'simulation'}</p>
          <p className="text-xs text-slate-600">scene {snapshot?.world.sceneId || '-'}</p>
        </div>
        <div className="text-xs text-slate-600">
          {loading ? 'loading' : `tick ${snapshot?.tick ?? '-'} • t=${snapshot?.timeSeconds ?? '-'}s • ${snapshot?.paused ? 'paused' : 'running'}`}
        </div>
        {error ? <p className="mt-1 text-xs text-amber-700">{error}</p> : null}
      </section>

      <Viewport3D />

      <AgentStatus />

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
          {snapshot?.perceivedNearby.length === 0 ? <p className="text-sm text-slate-500">no perceived entities</p> : null}
        </div>
        {selectedEntity ? (
          <div className="mt-2 rounded border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700">
            selected {selectedEntity.name} @ [{selectedEntity.position.map((n) => n.toFixed(2)).join(', ')}]
          </div>
        ) : null}
      </section>

      <EventTimeline />

      <BottomControls />
    </main>
  )
}

export default HomePage
