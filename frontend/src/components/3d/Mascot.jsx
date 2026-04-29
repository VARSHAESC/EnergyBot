import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { RoundedBox } from '@react-three/drei';

const WORN_METAL = { color: '#e2e8f0', roughness: 0.7, metalness: 0.3 };
const DARK_METAL = { color: '#334155', roughness: 0.8, metalness: 0.5 };
const TEAL_GLOW  = { color: '#00d4d4', emissive: '#00d4d4', emissiveIntensity: 3 };

export default function Mascot({ status = 'idle', mini = false }) {
  const rootRef       = useRef();
  const headRef       = useRef();
  const leftArmRef    = useRef();
  const rightArmRef   = useRef();
  const leftEyeRef    = useRef();
  const rightEyeRef   = useRef();

  // Randomize blinking
  const blinkOffset = useMemo(() => Math.random() * 5, []);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (!rootRef.current) return;

    // 1. Universal subtle float
    rootRef.current.position.y = Math.sin(t * 1.5) * 0.05 - 0.2; // shifted down a bit

    // 2. Slow blinking logic (quick shut and open)
    // t + offset modulo 5 seconds. If > 4.8, blink.
    const isBlinking = ((t + blinkOffset) % 5) > 4.85;
    const blinkScale = isBlinking ? 0.1 : 1;
    
    if (leftEyeRef.current && rightEyeRef.current) {
      // Scale Y to simulate eyelid
      leftEyeRef.current.scale.y = blinkScale;
      rightEyeRef.current.scale.y = blinkScale;
    }

    const mat1 = leftEyeRef.current?.material;
    const mat2 = rightEyeRef.current?.material;

    // 3. State-based animations
    if (status === 'idle') {
      // Gentle swaying
      rootRef.current.rotation.y = Math.sin(t * 0.5) * 0.15;
      
      // Subtle head tilt and look around
      headRef.current.rotation.z = Math.sin(t * 0.8) * 0.08;
      headRef.current.rotation.y = Math.sin(t * 0.6) * 0.15;
      headRef.current.rotation.x = Math.sin(t * 1.2) * 0.05 + 0.1; // look slightly up/down
      
      // Arms hanging relaxed
      leftArmRef.current.rotation.x = Math.sin(t * 1.1) * 0.05;
      rightArmRef.current.rotation.x = Math.cos(t * 1.1) * 0.05;
      
      if (mat1) { mat1.emissiveIntensity = 2.5; mat2.emissiveIntensity = 2.5; }

    } else if (status === 'thinking') {
      // Looking down and to the side, slight twitch
      rootRef.current.rotation.y = Math.sin(t * 0.3) * 0.1;
      
      headRef.current.rotation.z = Math.sin(t * 3) * 0.03 + 0.15; // tilted
      headRef.current.rotation.y = 0.2;
      headRef.current.rotation.x = -0.15 + Math.sin(t * 4) * 0.02; // looking down and thinking
      
      leftArmRef.current.rotation.x = -0.2;
      rightArmRef.current.rotation.x = Math.sin(t * 4) * 0.1 - 0.3; // tapping or thinking motion
      
      // Pulsing eyes
      const pulse = 1.5 + Math.sin(t * 6) * 1.5;
      if (mat1) { mat1.emissiveIntensity = pulse; mat2.emissiveIntensity = pulse; }

    } else if (status === 'success') {
      // Happy bounce and look up
      rootRef.current.position.y += Math.abs(Math.sin(t * 6)) * 0.08; // bouncy
      rootRef.current.rotation.y = Math.sin(t * 3) * 0.2;
      
      headRef.current.rotation.z = Math.sin(t * 4) * 0.1;
      headRef.current.rotation.y = 0;
      headRef.current.rotation.x = 0.25; // looking up happily
      
      // Arms waving up
      leftArmRef.current.rotation.x = -0.6 + Math.sin(t * 8) * 0.2;
      rightArmRef.current.rotation.x = -0.6 + Math.cos(t * 8) * 0.2;
      leftArmRef.current.rotation.z = -0.2;
      rightArmRef.current.rotation.z = 0.2;
      
      if (mat1) { mat1.emissiveIntensity = 4; mat2.emissiveIntensity = 4; }
    }
  });

  return (
    <group ref={rootRef} scale={1.4}>
      
      {/* ── BODY (Compact box) ── */}
      <RoundedBox args={[0.7, 0.65, 0.6]} radius={0.12} smoothness={4} castShadow position={[0, 0.1, 0]}>
        <meshStandardMaterial {...WORN_METAL} />
      </RoundedBox>
      
      {/* Body details / front panel */}
      <RoundedBox args={[0.4, 0.3, 0.05]} radius={0.05} smoothness={2} position={[0, 0.1, 0.31]}>
        <meshStandardMaterial {...DARK_METAL} color="#1e293b" />
      </RoundedBox>
      <mesh position={[-0.1, 0.15, 0.33]}>
        <circleGeometry args={[0.04, 16]} />
        <meshStandardMaterial color="#00d4d4" emissive="#00d4d4" emissiveIntensity={1} />
      </mesh>

      {/* ── NECK ── */}
      <mesh position={[0, 0.45, 0]}>
        <cylinderGeometry args={[0.06, 0.08, 0.15, 12]} />
        <meshStandardMaterial {...DARK_METAL} />
      </mesh>

      {/* ── HEAD (Pivot point at bottom of neck) ── */}
      <group ref={headRef} position={[0, 0.5, 0]}>
        
        {/* Left Eye Pod */}
        <group position={[-0.18, 0.15, 0.05]} rotation={[0, 0.15, 0]}>
          <RoundedBox args={[0.3, 0.28, 0.35]} radius={0.06} smoothness={3} castShadow>
            <meshStandardMaterial {...WORN_METAL} />
          </RoundedBox>
          {/* Lens cavity */}
          <mesh position={[0, 0, 0.18]} rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.1, 0.1, 0.02, 24]} />
            <meshStandardMaterial {...DARK_METAL} />
          </mesh>
          {/* Glowing Eye */}
          <mesh ref={leftEyeRef} position={[0, 0, 0.19]}>
            <sphereGeometry args={[0.07, 16, 16]} />
            <meshStandardMaterial {...TEAL_GLOW} />
          </mesh>
        </group>

        {/* Right Eye Pod */}
        <group position={[0.18, 0.15, 0.05]} rotation={[0, -0.15, 0]}>
          <RoundedBox args={[0.3, 0.28, 0.35]} radius={0.06} smoothness={3} castShadow>
            <meshStandardMaterial {...WORN_METAL} />
          </RoundedBox>
          {/* Lens cavity */}
          <mesh position={[0, 0, 0.18]} rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.1, 0.1, 0.02, 24]} />
            <meshStandardMaterial {...DARK_METAL} />
          </mesh>
          {/* Glowing Eye */}
          <mesh ref={rightEyeRef} position={[0, 0, 0.19]}>
            <sphereGeometry args={[0.07, 16, 16]} />
            <meshStandardMaterial {...TEAL_GLOW} />
          </mesh>
        </group>
      </group>

      {/* ── ARMS ── */}
      {/* Left Arm */}
      <group ref={leftArmRef} position={[-0.42, 0.15, 0]}>
        {/* Shoulder */}
        <mesh rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.08, 0.08, 0.1, 12]} />
          <meshStandardMaterial {...DARK_METAL} />
        </mesh>
        {/* Arm Segment */}
        <RoundedBox args={[0.06, 0.4, 0.08]} radius={0.02} smoothness={2} position={[-0.05, -0.15, 0.05]} rotation={[0.2, 0, 0]} castShadow>
          <meshStandardMaterial {...WORN_METAL} />
        </RoundedBox>
        {/* Claw/Hand */}
        <mesh position={[-0.05, -0.35, 0.1]}>
          <boxGeometry args={[0.04, 0.1, 0.12]} />
          <meshStandardMaterial {...DARK_METAL} />
        </mesh>
      </group>

      {/* Right Arm */}
      <group ref={rightArmRef} position={[0.42, 0.15, 0]}>
        {/* Shoulder */}
        <mesh rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.08, 0.08, 0.1, 12]} />
          <meshStandardMaterial {...DARK_METAL} />
        </mesh>
        {/* Arm Segment */}
        <RoundedBox args={[0.06, 0.4, 0.08]} radius={0.02} smoothness={2} position={[0.05, -0.15, 0.05]} rotation={[0.2, 0, 0]} castShadow>
          <meshStandardMaterial {...WORN_METAL} />
        </RoundedBox>
        {/* Claw/Hand */}
        <mesh position={[0.05, -0.35, 0.1]}>
          <boxGeometry args={[0.04, 0.1, 0.12]} />
          <meshStandardMaterial {...DARK_METAL} />
        </mesh>
      </group>

      {/* ── BASE (Treads) ── */}
      {/* Left Tread */}
      <RoundedBox args={[0.18, 0.22, 0.7]} radius={0.08} smoothness={3} position={[-0.28, -0.28, 0]} castShadow>
        <meshStandardMaterial {...DARK_METAL} color="#1e293b" />
      </RoundedBox>
      {/* Right Tread */}
      <RoundedBox args={[0.18, 0.22, 0.7]} radius={0.08} smoothness={3} position={[0.28, -0.28, 0]} castShadow>
        <meshStandardMaterial {...DARK_METAL} color="#1e293b" />
      </RoundedBox>

    </group>
  );
}

