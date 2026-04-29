import { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import Mascot from './Mascot';

export default function MiniBotPortal({ status = 'idle', size = 140 }) {
  return (
    <div
      style={{
        width: size,
        height: size,
        overflow: 'visible', // allow glow to extend
        flexShrink: 0,
        pointerEvents: 'none', // pass clicks through
      }}
    >
      <Canvas
        camera={{ position: [0, 0.4, 4.5], fov: 42 }}
        gl={{ antialias: true, alpha: true }}
        dpr={[1, 2]}
        style={{ background: 'transparent' }}
        onCreated={({ gl }) => gl.setClearColor(0, 0, 0, 0)}
      >
        <ambientLight intensity={0.6} />
        <directionalLight position={[3, 5, 2]} intensity={1.5} />
        <pointLight position={[0, 1.5, 2]} color="#00d4d4" intensity={2} distance={6} />

        <Suspense fallback={null}>
          <Mascot status={status} mini />
          {/* We only use OrbitControls if we wanted user interaction, 
              but since it's an assistant, we'll let Mascot handle all rotation and we disable controls. */}
        </Suspense>

        <EffectComposer>
          <Bloom intensity={2.5} luminanceThreshold={0.2} luminanceSmoothing={0.9} />
        </EffectComposer>
      </Canvas>
    </div>
  );
}

