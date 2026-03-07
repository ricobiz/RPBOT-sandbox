import { useGLTF, useAnimations, Capsule } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { useState } from 'react';

const CHARACTER_URL = 'https://example.com/character.glb';

export default function Character3D() {
  const [fallback, setFallback] = useState(false);
  let gltf: any = null;
  let animations: any[] = [];

  try {
    const result = useGLTF(CHARACTER_URL, true);
    gltf = result.scene;
    animations = result.animations;
  } catch (e) {
    console.warn('Failed to load character GLTF, falling back to Capsule', e);
    setFallback(true);
  }

  if (fallback || !gltf) {
    return <Capsule args={[1, 2, 32, 32]} />;
  }

  const { actions } = useAnimations(animations, gltf);

  // Play idle animation if available
  useFrame(() => {
    if (actions && actions.idle) {
      actions.idle.play();
    }
  });

  return <primitive object={gltf} />;
}
