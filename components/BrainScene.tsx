'use client'

import { Suspense, useState, useCallback, useMemo } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, PerspectiveCamera } from '@react-three/drei'
import { EffectComposer, Bloom } from '@react-three/postprocessing'
import LowPolyBrain from './LowPolyBrain'

// ── Default proficiency levels (fully dark until scored) ──
const DEMO_PROFICIENCY: Record<string, number> = {
  Region_Fundamentals:  0.0,
  Region_OOP:           0.0,
  Region_DataStructures:0.0,
  Region_Algorithms:    0.0,
  Region_Systems:       0.0,
  Region_Frontend:      0.0,
  Region_DevPractices:  0.0,
  Region_Product:       0.0,
  Region_Hackathon:     0.0,
}

function Scene({
  activeRegions,
  proficiencyLevels,
  onRegionHover,
  onRegionClick,
}: {
  activeRegions?: Set<string>
  proficiencyLevels?: Record<string, number>
  onRegionHover?: (id: string | null) => void
  onRegionClick?: (id: string) => void
}) {
  return (
    <>
      <PerspectiveCamera makeDefault position={[0, 0.3, 3.8]} fov={45} />

      <ambientLight intensity={0.15} />
      <directionalLight position={[5, 5, 5]} intensity={0.3} color="#ffffff" />
      <directionalLight position={[-5, 3, -5]} intensity={0.2} color="#6366f1" />
      <pointLight position={[0, 2, 4]} intensity={0.25} color="#60a5fa" />

      <Suspense fallback={null}>
        <LowPolyBrain
          activeRegions={activeRegions}
          proficiencyLevels={proficiencyLevels}
          onRegionHover={onRegionHover}
          onRegionClick={onRegionClick}
        />
      </Suspense>

      <OrbitControls
        enableZoom={false}
        enablePan={false}
        enableRotate={true}
        autoRotate
        autoRotateSpeed={0.8}
        enableDamping
        dampingFactor={0.08}
      />

      <EffectComposer>
        <Bloom
          intensity={0.8}
          luminanceThreshold={0.25}
          luminanceSmoothing={0.5}
          mipmapBlur
        />
      </EffectComposer>
    </>
  )
}

export default function BrainScene() {
  const [hoveredRegion, setHoveredRegion] = useState<string | null>(null)

  // In idle / demo mode, no specific set of active regions — all glow at base level
  // When a region is hovered, highlight that region
  const activeRegions = useMemo(() => {
    if (hoveredRegion) return new Set([hoveredRegion])
    return undefined // all regions get base glow
  }, [hoveredRegion])

  const handleRegionHover = useCallback((id: string | null) => {
    setHoveredRegion(id)
  }, [])

  const handleRegionClick = useCallback((id: string) => {
    console.log('Region clicked:', id)
  }, [])

  return (
    <div className="canvas-container">
      <Canvas
        gl={{
          antialias: true,
          alpha: true,
          powerPreference: 'high-performance',
        }}
        style={{ background: '#000000' }}
      >
        <Scene
          activeRegions={activeRegions}
          proficiencyLevels={DEMO_PROFICIENCY}
          onRegionHover={handleRegionHover}
          onRegionClick={handleRegionClick}
        />
      </Canvas>

      {/* Region label tooltip */}
      {hoveredRegion && (
        <div className="absolute top-6 right-6 bg-black/60 border border-white/10 rounded-lg px-4 py-2 text-white/80 text-sm font-medium backdrop-blur-sm pointer-events-none">
          {hoveredRegion.replace('Region_', '')}
        </div>
      )}
    </div>
  )
}
