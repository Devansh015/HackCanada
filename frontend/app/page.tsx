'use client'

import { useState } from 'react'
import dynamic from 'next/dynamic'
import { useProfile } from '@/context/ProfileContext'
import UploadPanel from '@/components/UploadPanel'

// Dynamic import for Three.js components (requires client-side only)
const BrainScene = dynamic(() => import('@/components/BrainScene'), {
  ssr: false,
  loading: () => (
    <div className="canvas-container flex items-center justify-center bg-black">
      <div className="text-white/30 text-sm">Loading neural network...</div>
    </div>
  )
})

export default function Home() {
  const { regionScores, isLoading, profile, resetSession } = useProfile()
  const [showUploadPanel, setShowUploadPanel] = useState(false)
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null)

  const handleRegionClick = (regionId: string) => {
    setSelectedRegion(regionId)
    // Could open a detail panel here
  }

  return (
    <main className="relative min-h-screen bg-black overflow-hidden">
      {/* 3D Brain Background */}
      <BrainScene 
        proficiencyLevels={regionScores}
        onRegionClick={handleRegionClick}
      />
      
      {/* Hero Content Overlay */}
      <div className="hero-content relative z-10 min-h-screen flex flex-col justify-between p-6 md:p-12 pointer-events-none">
        {/* Header */}
        <header className="flex items-center justify-between pointer-events-auto">
          <div className="text-white/90 font-semibold text-xl tracking-tight">
            LUMAS
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={resetSession}
              className="px-4 py-2 bg-white/5 hover:bg-white/15 border border-white/10 rounded-lg text-white/70 hover:text-white text-sm font-medium transition-colors flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Create New Session
            </button>
            <button
              onClick={() => setShowUploadPanel(true)}
              className="px-4 py-2 bg-white/10 hover:bg-white/20 border border-white/20 rounded-lg text-white text-sm font-medium transition-colors flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add Project
            </button>
          </div>
        </header>
        
        {/* Main Hero Text */}
        <div className="flex-1" />
        
        {/* Footer */}
        <footer className="flex items-end justify-between pointer-events-auto">
          <div className="text-white/30 text-xs">
            © 2026 Lumas
          </div>
        </footer>
      </div>

      {/* Upload Panel Modal */}
      {showUploadPanel && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <div 
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setShowUploadPanel(false)}
          />
          {/* Panel */}
          <div className="relative z-10">
            <UploadPanel onClose={() => setShowUploadPanel(false)} />
          </div>
        </div>
      )}

      {/* Selected Region Info (optional future feature) */}
      {selectedRegion && (
        <div className="fixed bottom-6 left-6 z-40 bg-black/80 backdrop-blur-xl border border-white/10 rounded-lg px-4 py-3 text-white text-sm">
          <div className="font-medium">{selectedRegion.replace('Region_', '')}</div>
          <div className="text-white/50 text-xs">
            Proficiency: {Math.round((regionScores[selectedRegion as keyof typeof regionScores] ?? 0) * 100)}%
          </div>
          <button 
            onClick={() => setSelectedRegion(null)}
            className="absolute top-1 right-1 text-white/30 hover:text-white/60"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}
    </main>
  )
}
