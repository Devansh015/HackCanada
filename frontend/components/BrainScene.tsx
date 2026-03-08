'use client'

import { Suspense, useState, useCallback, useMemo } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, PerspectiveCamera } from '@react-three/drei'
import LowPolyBrain from './LowPolyBrain'

// ── Default proficiency levels (fallback when no data) ──────────
const DEFAULT_PROFICIENCY: Record<string, number> = {
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

export interface BrainSceneProps {
  proficiencyLevels?: Record<string, number>
  onRegionClick?: (regionId: string) => void
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


    </>
  )
}

export default function BrainScene({ 
  proficiencyLevels,
  onRegionClick: externalOnRegionClick,
}: BrainSceneProps = {}) {
  const [hoveredRegion, setHoveredRegion] = useState<string | null>(null)
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })

  // Track mouse position for tooltip
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    setMousePos({ x: e.clientX, y: e.clientY })
  }, [])

  // Merge provided proficiency with defaults
  const mergedProficiency = useMemo(() => ({
    ...DEFAULT_PROFICIENCY,
    ...proficiencyLevels,
  }), [proficiencyLevels])

  // Don't restrict active regions on hover — the hover highlight is handled
  // internally by LowPolyBrain's own hoveredRegion state. Setting activeRegions
  // here would dim all other regions and wipe out the proficiency glow.
  const activeRegions = undefined

  const handleRegionHover = useCallback((id: string | null) => {
    setHoveredRegion(id)
  }, [])

  const handleRegionClick = useCallback((id: string) => {
    console.log('Region clicked:', id)
    externalOnRegionClick?.(id)
  }, [externalOnRegionClick])

  return (
    <div className="canvas-container" onMouseMove={handleMouseMove}>
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
          proficiencyLevels={mergedProficiency}
          onRegionHover={handleRegionHover}
          onRegionClick={handleRegionClick}
        />
      </Canvas>


    </div>
  )
}
