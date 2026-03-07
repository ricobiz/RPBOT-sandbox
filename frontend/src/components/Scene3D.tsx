import { Canvas } from '@react-three/fiber';
import { OrbitControls, Environment, Plane } from '@react-three/drei';
import { Suspense } from 'react';
import Character3D from './Character3D';
import SceneOverlay from './SceneOverlay';

export default function Scene3D() {
  return (
    <div style={{ width: '100%', height: '100vh', position: 'relative' }}>
      <Canvas shadows camera={{ position: [0, 2, 5], fov: 60 }}>
        <color attach="background" args={['#111']} />
        <Suspense fallback={null}>
          <ambientLight intensity={0.5} />
          <directionalLight
            castShadow
            position={[5, 10, 5]}
            intensity={1}
            shadow-mapSize-width={1024}
            shadow-mapSize-height={1024}
          />
          <Plane
            rotation={[-Math.PI / 2, 0, 0]}
            receiveShadow
            position={[0, 0, 0]}
            args={[10, 10]}
          />
          <Character3D />
          <Environment preset="night" background={false} />
          <OrbitControls />
        </Suspense>
      </Canvas>
      <SceneOverlay />
    </div>
  );
}
