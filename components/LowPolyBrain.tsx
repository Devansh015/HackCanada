'use client'

import { useRef, useEffect, useState, useMemo, useCallback } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

// ── Types ─────────────────────────────────────────────────
interface RegionData {
  id: string
  label: string
  color: string
  nodeCount: number
  nodeIds: number[]
  center: [number, number, number]
}

interface NodeData {
  id: number
  position: [number, number, number]
  region: number
}

interface BrainData {
  meta: { totalNodes: number; totalEdges: number }
  regions: RegionData[]
  nodes: NodeData[]
  edges: [number, number][]
  interRegionPaths: [number, number][]
}

// ── Particle system for signal travel ─────────────────────
const PARTICLE_COUNT = 150

interface Particle {
  edgeIdx: number
  t: number
  speed: number
  regionSource: number
}

// ── Component ─────────────────────────────────────────────

interface LowPolyBrainProps {
  activeRegions?: Set<string>
  proficiencyLevels?: Record<string, number>   // 0–1 per region id
  onRegionHover?: (regionId: string | null) => void
  onRegionClick?: (regionId: string) => void
}

export default function LowPolyBrain({
  activeRegions,
  proficiencyLevels,
  onRegionHover,
  onRegionClick,
}: LowPolyBrainProps) {
  const groupRef = useRef<THREE.Group>(null)
  const edgeLinesRef = useRef<THREE.LineSegments>(null)
  const nodesRef = useRef<THREE.Points>(null)
  const particlesRef = useRef<THREE.Points>(null)
  const [data, setData] = useState<BrainData | null>(null)
  const [hoveredRegion, setHoveredRegion] = useState<number | null>(null)

  // Load brain region data
  useEffect(() => {
    fetch('/brain_regions.json')
      .then((r) => r.json())
      .then((d: BrainData) => setData(d))
  }, [])

  // ── Build geometries from data ──────────────────────────
  const {
    edgeGeometry,
    edgeColors,
    nodePositions,
    nodeColors,
    nodeSizes,
    nodeRegionIds,
    particlePositions,
    particlesData,
  } = useMemo(() => {
    if (!data) return {} as any

    const { nodes, edges, regions } = data
    const regionColors = regions.map((r) => new THREE.Color(r.color))

    // ─ Edge lines ─────────────────────────────────────────
    const edgeVerts = new Float32Array(edges.length * 6)
    const edgeCols = new Float32Array(edges.length * 6)
    for (let i = 0; i < edges.length; i++) {
      const [a, b] = edges[i]
      const pa = nodes[a].position
      const pb = nodes[b].position
      edgeVerts[i * 6 + 0] = pa[0]; edgeVerts[i * 6 + 1] = pa[1]; edgeVerts[i * 6 + 2] = pa[2]
      edgeVerts[i * 6 + 3] = pb[0]; edgeVerts[i * 6 + 4] = pb[1]; edgeVerts[i * 6 + 5] = pb[2]

      // Blend colours of the two endpoints
      const ca = regionColors[nodes[a].region]
      const cb = regionColors[nodes[b].region]
      edgeCols[i * 6 + 0] = ca.r; edgeCols[i * 6 + 1] = ca.g; edgeCols[i * 6 + 2] = ca.b
      edgeCols[i * 6 + 3] = cb.r; edgeCols[i * 6 + 4] = cb.g; edgeCols[i * 6 + 5] = cb.b
    }
    const eGeo = new THREE.BufferGeometry()
    eGeo.setAttribute('position', new THREE.Float32BufferAttribute(edgeVerts, 3))
    eGeo.setAttribute('color', new THREE.Float32BufferAttribute(edgeCols, 3))

    // ─ Node points ────────────────────────────────────────
    const nPos = new Float32Array(nodes.length * 3)
    const nCol = new Float32Array(nodes.length * 3)
    const nSize = new Float32Array(nodes.length)
    const nRegion = new Int32Array(nodes.length)
    for (let i = 0; i < nodes.length; i++) {
      const p = nodes[i].position
      const c = regionColors[nodes[i].region]
      nPos[i * 3] = p[0]; nPos[i * 3 + 1] = p[1]; nPos[i * 3 + 2] = p[2]
      nCol[i * 3] = c.r; nCol[i * 3 + 1] = c.g; nCol[i * 3 + 2] = c.b
      nSize[i] = 0.018
      nRegion[i] = nodes[i].region
    }

    // ─ Particles ──────────────────────────────────────────
    const pPos = new Float32Array(PARTICLE_COUNT * 3)
    const parts: Particle[] = []
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const edgeIdx = Math.floor(Math.random() * edges.length)
      const [a] = edges[edgeIdx]
      parts.push({
        edgeIdx,
        t: Math.random(),
        speed: 0.15 + Math.random() * 0.35,
        regionSource: nodes[a].region,
      })
    }

    return {
      edgeGeometry: eGeo,
      edgeColors: edgeCols,
      nodePositions: nPos,
      nodeColors: nCol,
      nodeSizes: nSize,
      nodeRegionIds: nRegion,
      particlePositions: pPos,
      particlesData: parts,
    }
  }, [data])

  // ── Animate ─────────────────────────────────────────────
  useFrame((state) => {
    if (!data || !particlesRef.current || !nodesRef.current || !edgeLinesRef.current) return

    const time = state.clock.getElapsedTime()
    const dt = state.clock.getDelta()
    const { nodes, edges, regions } = data

    // Determine which region indices are "active"
    const activeIdxSet = new Set<number>()
    if (activeRegions) {
      regions.forEach((r, i) => { if (activeRegions.has(r.id)) activeIdxSet.add(i) })
    }
    const anyActive = activeIdxSet.size > 0

    // ── Update node colours & sizes based on activation ──
    const nCol = nodesRef.current.geometry.attributes.color as THREE.BufferAttribute
    const nSize = nodesRef.current.geometry.attributes.size as THREE.BufferAttribute
    const regionColors = regions.map((r) => new THREE.Color(r.color))
    const dimColor = new THREE.Color('#1a2a3a')

    for (let i = 0; i < nodes.length; i++) {
      const ri = nodes[i].region
      const active = !anyActive || activeIdxSet.has(ri)
      const hoverBright = hoveredRegion === ri
      const proficiency = proficiencyLevels?.[regions[ri].id] ?? (anyActive && active ? 0.7 : 0.35)
      const intensity = active ? proficiency : 0.08

      const baseColor = regionColors[ri]
      const color = active ? baseColor.clone() : dimColor.clone()

      // Pulse for active nodes
      if (active) {
        const pulse = Math.sin(time * 2.0 + i * 0.3) * 0.15 + 0.85
        color.multiplyScalar(intensity * pulse * (hoverBright ? 1.4 : 1.0))
      } else {
        color.multiplyScalar(intensity)
      }

      nCol.array[i * 3] = color.r
      nCol.array[i * 3 + 1] = color.g
      nCol.array[i * 3 + 2] = color.b

      // Size: bigger when active
      const baseSize = active ? 0.022 + proficiency * 0.012 : 0.012
      const sizePulse = active ? Math.sin(time * 1.5 + i * 0.5) * 0.003 + 1 : 1
      ;(nSize.array as Float32Array)[i] = baseSize * sizePulse * (hoverBright ? 1.3 : 1.0)
    }
    nCol.needsUpdate = true
    nSize.needsUpdate = true

    // ── Update edge colours ───────────────────────────────
    const eCol = edgeLinesRef.current.geometry.attributes.color as THREE.BufferAttribute
    for (let i = 0; i < edges.length; i++) {
      const [a, b] = edges[i]
      const ra = nodes[a].region, rb = nodes[b].region
      const aActive = !anyActive || activeIdxSet.has(ra)
      const bActive = !anyActive || activeIdxSet.has(rb)
      const profA = proficiencyLevels?.[regions[ra].id] ?? (aActive ? 0.5 : 0.1)
      const profB = proficiencyLevels?.[regions[rb].id] ?? (bActive ? 0.5 : 0.1)

      const ca = aActive ? regionColors[ra].clone().multiplyScalar(profA * 0.45) : dimColor.clone().multiplyScalar(0.08)
      const cb = bActive ? regionColors[rb].clone().multiplyScalar(profB * 0.45) : dimColor.clone().multiplyScalar(0.08)

      eCol.array[i * 6 + 0] = ca.r; eCol.array[i * 6 + 1] = ca.g; eCol.array[i * 6 + 2] = ca.b
      eCol.array[i * 6 + 3] = cb.r; eCol.array[i * 6 + 4] = cb.g; eCol.array[i * 6 + 5] = cb.b
    }
    eCol.needsUpdate = true

    // ── Animate particles along edges ─────────────────────
    const pPos = particlesRef.current.geometry.attributes.position as THREE.BufferAttribute
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const p = particlesData[i]
      p.t += p.speed * dt

      if (p.t >= 1) {
        // Hop to a connected edge
        const [, endNode] = edges[p.edgeIdx]
        const connected = edges.reduce<number[]>((acc, e, idx) => {
          if (e[0] === endNode || e[1] === endNode) acc.push(idx)
          return acc
        }, [])
        p.edgeIdx = connected[Math.floor(Math.random() * connected.length)] ?? Math.floor(Math.random() * edges.length)
        p.t = 0
        p.regionSource = nodes[edges[p.edgeIdx][0]].region
      }

      const [ea, eb] = edges[p.edgeIdx]
      const pa = nodes[ea].position, pb = nodes[eb].position
      const t = p.t
      pPos.array[i * 3 + 0] = pa[0] + (pb[0] - pa[0]) * t
      pPos.array[i * 3 + 1] = pa[1] + (pb[1] - pa[1]) * t
      pPos.array[i * 3 + 2] = pa[2] + (pb[2] - pa[2]) * t
    }
    pPos.needsUpdate = true
  })

  // ── Hover detection via raycasting on nodes ─────────────
  const handlePointerMove = useCallback(
    (e: any) => {
      if (!data || !nodesRef.current) return
      e.stopPropagation()
      const inter = e.intersections?.[0]
      if (inter && inter.index != null) {
        const idx = inter.index
        const ri = data.nodes[idx]?.region ?? null
        setHoveredRegion(ri)
        if (ri !== null) onRegionHover?.(data.regions[ri].id)
      }
    },
    [data, onRegionHover],
  )

  const handlePointerOut = useCallback(() => {
    setHoveredRegion(null)
    onRegionHover?.(null)
  }, [onRegionHover])

  const handleClick = useCallback(
    (e: any) => {
      if (!data) return
      e.stopPropagation()
      const inter = e.intersections?.[0]
      if (inter && inter.index != null) {
        const ri = data.nodes[inter.index]?.region
        if (ri != null) onRegionClick?.(data.regions[ri].id)
      }
    },
    [data, onRegionClick],
  )

  if (!data || !edgeGeometry) return null

  return (
    <group ref={groupRef} rotation={[0, -Math.PI / 2, 0]}>
      {/* Edge connection lines */}
      <lineSegments ref={edgeLinesRef} geometry={edgeGeometry}>
        <lineBasicMaterial vertexColors transparent opacity={0.35} depthWrite={false} />
      </lineSegments>

      {/* Node points (interactive) */}
      <points
        ref={nodesRef}
        onPointerMove={handlePointerMove}
        onPointerOut={handlePointerOut}
        onClick={handleClick}
      >
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            array={nodePositions}
            count={data.nodes.length}
            itemSize={3}
          />
          <bufferAttribute
            attach="attributes-color"
            array={nodeColors}
            count={data.nodes.length}
            itemSize={3}
          />
          <bufferAttribute
            attach="attributes-size"
            array={nodeSizes}
            count={data.nodes.length}
            itemSize={1}
          />
        </bufferGeometry>
        <pointsMaterial
          vertexColors
          size={0.02}
          sizeAttenuation
          transparent
          opacity={0.9}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>

      {/* Signal particles */}
      <points ref={particlesRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            array={particlePositions}
            count={PARTICLE_COUNT}
            itemSize={3}
          />
        </bufferGeometry>
        <pointsMaterial
          color="#ffffff"
          size={0.025}
          sizeAttenuation
          transparent
          opacity={0.85}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>
    </group>
  )
}
