'use client'

import { useState, useRef, useEffect } from 'react'
import dynamic from 'next/dynamic'
import { useProfile } from '@/context/ProfileContext'
import UploadPanel from '@/components/UploadPanel'
import ChatBot from '@/components/ChatBot'
import { useCallback } from 'react'

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
  const [triggerAnimation, setTriggerAnimation] = useState(false)
  const [chatPanelOpen, setChatPanelOpen] = useState(false)
  const scoresChangedWhilePanelOpen = useRef(false)
  const prevScoresRef = useRef(regionScores)

  const handleChatPanelToggle = useCallback((open: boolean) => {
    setChatPanelOpen(open)
  }, [])

  // Detect score changes while panel is open
  useEffect(() => {
    if (showUploadPanel && prevScoresRef.current !== regionScores) {
      scoresChangedWhilePanelOpen.current = true
    }
    prevScoresRef.current = regionScores
  }, [regionScores, showUploadPanel])

  const handleCloseUploadPanel = () => {
    setShowUploadPanel(false)
    if (scoresChangedWhilePanelOpen.current) {
      scoresChangedWhilePanelOpen.current = false
      // Trigger BFS animation now that panel is closed
      setTriggerAnimation(true)
      // Reset trigger after a short delay so it can be re-triggered later
      setTimeout(() => setTriggerAnimation(false), 100)
    }
  }

  const handleRegionClick = (regionId: string) => {
    setSelectedRegion(regionId)
    // Could open a detail panel here
  }

  return (
    <main className="relative min-h-screen bg-black overflow-hidden">
      {/* 3D Brain Background */}
      <BrainScene 
        proficiencyLevels={regionScores}
        triggerAnimation={triggerAnimation}
        onRegionClick={handleRegionClick}
      />
      
      {/* Hero Content Overlay */}
      <div className="hero-content relative z-10 min-h-screen flex flex-col justify-between p-4 sm:p-6 md:p-12 pb-20 sm:pb-6 md:pb-12 pointer-events-none">
        {/* Header */}
        <header className="flex items-center justify-between pointer-events-auto">
          <div className="text-white/90 font-semibold text-lg sm:text-xl tracking-tight">
            CORTEX
          </div>
          <div className={`flex items-center gap-2 sm:gap-3 transition-all duration-300 ${chatPanelOpen ? 'sm:mr-[320px] md:mr-[396px]' : ''}`}>
            <button
              onClick={resetSession}
              className="px-3 sm:px-4 py-2 sm:py-2.5 bg-white/10 hover:bg-white/20 border border-white/20 rounded-lg text-white text-xs sm:text-sm font-medium transition-colors flex items-center gap-1.5 sm:gap-2"
            >
              <svg className="w-3.5 h-3.5 sm:w-4 sm:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H16" />
              </svg>
              <span className="hidden sm:inline">New Session</span>
              <span className="sm:hidden">New</span>
            </button>
            <button
              onClick={() => setShowUploadPanel(true)}
              className="px-3 sm:px-4 py-2 sm:py-2.5 bg-white/10 hover:bg-white/20 border border-white/20 rounded-lg text-white text-xs sm:text-sm font-medium transition-colors flex items-center gap-1.5 sm:gap-2"
            >
              <svg className="w-3.5 h-3.5 sm:w-4 sm:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              <span className="hidden sm:inline">Add Project</span>
              <span className="sm:hidden">Add</span>
            </button>
          </div>
        </header>
        
        {/* Main Hero Text */}
        <div className="flex-1" />
        
        {/* Footer - hidden on mobile to avoid chat bar overlap */}
        <footer className="hidden sm:flex items-end justify-between pointer-events-auto">
          <div className="text-white/30 text-xs">
            © 2026 Cortex
          </div>
        </footer>
      </div>

      {/* Upload Panel Modal */}
      {showUploadPanel && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
          {/* Backdrop */}
          <div 
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => handleCloseUploadPanel()}
          />
          {/* Panel */}
          <div className="relative z-10 w-full sm:w-auto max-h-[90vh] overflow-y-auto">
            <UploadPanel onClose={handleCloseUploadPanel} />
          </div>
        </div>
      )}

      {/* Selected Region Info (optional future feature) */}
      {selectedRegion && (
        <div className="fixed bottom-24 sm:bottom-28 left-4 sm:left-8 z-40 bg-black/80 backdrop-blur-xl border border-white/15 rounded-xl px-4 sm:px-6 py-3 sm:py-4 text-white max-w-[200px] sm:max-w-[240px]">
          <div className="font-semibold text-sm sm:text-base pr-6">{selectedRegion.replace('Region_', '')}</div>
          <div className="text-white/60 text-xs sm:text-sm mt-1">
            Proficiency: {Math.round((regionScores[selectedRegion as keyof typeof regionScores] ?? 0) * 100)}%
          </div>
          <button 
            onClick={() => setSelectedRegion(null)}
            className="absolute top-2 right-2 text-white/40 hover:text-white/70 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* AI Chatbot */}
      <ChatBot onPanelToggle={handleChatPanelToggle} />
    </main>
  )
}
