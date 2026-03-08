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
  const { regionScores, isLoading, profile } = useProfile()
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
          <button
            onClick={() => setShowUploadPanel(true)}
            className="px-4 py-2 bg-white/10 hover:bg-white/20 border border-white/20 rounded-lg text-white text-sm font-medium transition-colors flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add Project
          </button>
        </header>
        
        {/* Main Hero Text */}
        <div className="flex-1 flex items-center justify-start md:justify-start pointer-events-auto">
          <div className="max-w-xl">
            <h1 className="text-4xl md:text-6xl font-light text-white text-glow leading-tight mb-6">
              Your Skills
              <br />
              <span className="text-white/40">Visualized</span>
            </h1>
            <p className="text-white/50 text-lg md:text-xl font-light leading-relaxed mb-8">
              {profile && profile.upload_count > 0 ? (
                <>
                  Each region represents a skill area. 
                  Brightness shows your proficiency based on {profile.upload_count} analyzed project{profile.upload_count > 1 ? 's' : ''}.
                </>
              ) : (
                <>
                  Add your projects to see how your skills connect. 
                  Each region will light up based on what you've built.
                </>
              )}
            </p>
            
            {/* Dynamic Legend based on actual scores */}
            <div className="flex items-center gap-6 text-sm text-white/40">
              {isLoading ? (
                <span className="text-white/30">Loading profile...</span>
              ) : (
                <>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-white/30 pulse-indicator"></span>
                    <span>Learning</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-white/60"></span>
                    <span>Developing</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-white shadow-[0_0_10px_rgba(255,255,255,0.5)]"></span>
                    <span>Proficient</span>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
        
        {/* Footer */}
        <footer className="flex items-end justify-between pointer-events-auto">
          <div className="text-white/30 text-xs">
            © 2026 Lumas
          </div>
          <div className="text-white/30 text-xs text-right">
            <div>Skills mapped from your projects</div>
            <div className="text-white/20">AI-powered analysis</div>
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
