'use client'

import { useState, useCallback, type FormEvent, type DragEvent } from 'react'
import { useProfile } from '@/context/ProfileContext'

interface UploadPanelProps {
  onClose?: () => void
}

export default function UploadPanel({ onClose }: UploadPanelProps) {
  const { uploadGitHubRepo, uploadPdf, isUploading, error, lastUpdate, clearError } = useProfile()

  const [githubUrl, setGithubUrl] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [uploadSuccess, setUploadSuccess] = useState(false)

  // Handle GitHub URL submission
  const handleGitHubSubmit = useCallback(async (e: FormEvent) => {
    e.preventDefault()
    if (!githubUrl.trim() || isUploading) return

    try {
      await uploadGitHubRepo(githubUrl)
      setGithubUrl('')
      setUploadSuccess(true)
      setTimeout(() => setUploadSuccess(false), 3000)
    } catch {
      // Error is handled in context
    }
  }, [githubUrl, isUploading, uploadGitHubRepo])

  // Handle PDF drag and drop
  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback(async (e: DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const file = e.dataTransfer.files[0]
    if (!file || !file.name.endsWith('.pdf')) {
      return
    }

    // Read PDF as text (simplified - in production, send as base64 or form data)
    const reader = new FileReader()
    reader.onload = async () => {
      const content = reader.result as string
      try {
        await uploadPdf(content, file.name)
        setUploadSuccess(true)
        setTimeout(() => setUploadSuccess(false), 3000)
      } catch {
        // Error handled in context
      }
    }
    reader.readAsText(file)
  }, [uploadPdf])

  // Handle file input change
  const handleFileChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = async () => {
      const content = reader.result as string
      try {
        await uploadPdf(content, file.name)
        setUploadSuccess(true)
        setTimeout(() => setUploadSuccess(false), 3000)
      } catch {
        // Error handled in context
      }
    }
    reader.readAsText(file)
  }, [uploadPdf])

  return (
    <div className="bg-black/80 backdrop-blur-xl border border-white/10 rounded-2xl p-6 w-full max-w-md">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-white text-lg font-medium">Add Project</h2>
        {onClose && (
          <button
            onClick={onClose}
            className="text-white/40 hover:text-white/80 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Error message */}
      {error && (
        <div className="mb-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-300 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={clearError} className="text-red-300 hover:text-red-100">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* Success message */}
      {uploadSuccess && lastUpdate && (
        <div className="mb-4 p-3 bg-green-500/20 border border-green-500/30 rounded-lg text-green-300 text-sm">
          <div className="font-medium mb-1">Analysis complete!</div>
          <div className="text-green-300/70 text-xs">
            {lastUpdate.categories_increased.length} categories improved
          </div>
        </div>
      )}

      {/* GitHub URL Input */}
      <form onSubmit={handleGitHubSubmit} className="mb-6">
        <label className="block text-white/60 text-sm mb-2">GitHub Repository</label>
        <div className="flex gap-2">
          <input
            type="url"
            value={githubUrl}
            onChange={(e) => setGithubUrl(e.target.value)}
            placeholder="https://github.com/owner/repo"
            className="flex-1 bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white placeholder-white/30 text-sm focus:outline-none focus:border-white/30 transition-colors"
            disabled={isUploading}
          />
          <button
            type="submit"
            disabled={isUploading || !githubUrl.trim()}
            className="px-4 py-3 bg-white/10 hover:bg-white/20 disabled:bg-white/5 disabled:text-white/30 border border-white/10 rounded-lg text-white text-sm font-medium transition-colors"
          >
            {isUploading ? (
              <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              'Analyze'
            )}
          </button>
        </div>
      </form>

      {/* Divider */}
      <div className="flex items-center gap-4 mb-6">
        <div className="flex-1 h-px bg-white/10" />
        <span className="text-white/30 text-xs">or</span>
        <div className="flex-1 h-px bg-white/10" />
      </div>

      {/* PDF Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer
          ${isDragging 
            ? 'border-blue-500/50 bg-blue-500/10' 
            : 'border-white/10 hover:border-white/20 hover:bg-white/5'
          }
          ${isUploading ? 'opacity-50 pointer-events-none' : ''}
        `}
      >
        <input
          type="file"
          accept=".pdf"
          onChange={handleFileChange}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          disabled={isUploading}
        />
        <div className="text-white/40 mb-2">
          <svg className="w-8 h-8 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
        </div>
        <div className="text-white/60 text-sm">Drop PDF here</div>
        <div className="text-white/30 text-xs mt-1">or click to browse</div>
      </div>

      {/* Loading overlay */}
      {isUploading && (
        <div className="mt-4 flex items-center justify-center gap-2 text-white/60 text-sm">
          <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span>Analyzing with AI...</span>
        </div>
      )}
    </div>
  )
}
