'use client'

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  type ReactNode,
} from 'react'

import type { UserProfile, ProfileUpdateSummary, UploadScoreSnapshot } from '@/types/api'
import {
  getOrCreateProfile,
  scoreUpload,
  getUploadHistory,
  getStoredUserId,
  parseGitHubUrl,
  resetProfile,
} from '@/lib/api'
import {
  aggregateToRegions,
  type FrontendRegion,
} from '@/lib/categoryMapping'

// ── Types ─────────────────────────────────────────────────

interface ProfileState {
  userId: string
  profile: UserProfile | null
  regionScores: Record<FrontendRegion, number>
  uploads: UploadScoreSnapshot[]
  isLoading: boolean
  isUploading: boolean
  error: string | null
  lastUpdate: ProfileUpdateSummary | null
}

interface ProfileContextValue extends ProfileState {
  refreshProfile: () => Promise<void>
  uploadGitHubRepo: (url: string) => Promise<ProfileUpdateSummary>
  uploadPdf: (content: string, filename: string) => Promise<ProfileUpdateSummary>
  resetSession: () => Promise<void>
  clearError: () => void
}

const ProfileContext = createContext<ProfileContextValue | null>(null)

// ── Provider ──────────────────────────────────────────────

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ProfileState>({
    userId: '',
    profile: null,
    regionScores: {} as Record<FrontendRegion, number>,
    uploads: [],
    isLoading: true,
    isUploading: false,
    error: null,
    lastUpdate: null,
  })

  // Initialize user ID and fetch profile on mount
  useEffect(() => {
    const userId = getStoredUserId()
    setState(s => ({ ...s, userId }))

    async function init() {
      try {
        const profile = await getOrCreateProfile(userId)
        const history = await getUploadHistory(userId).catch(() => [])
        const regionScores = aggregateToRegions(profile.category_scores)

        setState(s => ({
          ...s,
          profile,
          regionScores,
          uploads: history || [],
          isLoading: false,
          error: null,
        }))
      } catch (err) {
        console.error('Failed to load profile:', err)
        setState(s => ({
          ...s,
          isLoading: false,
          error: err instanceof Error ? err.message : 'Failed to load profile',
        }))
      }
    }

    init()
  }, [])

  // Refresh profile from API
  const refreshProfile = useCallback(async () => {
    if (!state.userId) return

    setState(s => ({ ...s, isLoading: true }))
    try {
      const profile = await getOrCreateProfile(state.userId)
      const history = await getUploadHistory(state.userId).catch(() => [])
      const regionScores = aggregateToRegions(profile.category_scores)

      setState(s => ({
        ...s,
        profile,
        regionScores,
        uploads: history || [],
        isLoading: false,
        error: null,
      }))
    } catch (err) {
      setState(s => ({
        ...s,
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to refresh profile',
      }))
    }
  }, [state.userId])

  // Upload a GitHub repo for analysis
  const uploadGitHubRepo = useCallback(async (url: string): Promise<ProfileUpdateSummary> => {
    const parsed = parseGitHubUrl(url)
    if (!parsed) {
      throw new Error('Invalid GitHub URL. Use format: https://github.com/owner/repo')
    }

    setState(s => ({ ...s, isUploading: true, error: null }))

    try {
      const result = await scoreUpload(state.userId, {
        source_type: 'github_repo',
        content: url,
      })

      // Update local state with new scores
      const regionScores = aggregateToRegions(result.profile_after)
      setState(s => ({
        ...s,
        profile: s.profile ? { ...s.profile, category_scores: result.profile_after } : null,
        regionScores,
        isUploading: false,
        lastUpdate: result,
      }))

      // Refresh full history
      refreshProfile()

      return result
    } catch (err) {
      setState(s => ({
        ...s,
        isUploading: false,
        error: err instanceof Error ? err.message : 'Failed to analyze repository',
      }))
      throw err
    }
  }, [state.userId, refreshProfile])

  // Upload PDF content for analysis
  const uploadPdf = useCallback(async (
    content: string,
    filename: string
  ): Promise<ProfileUpdateSummary> => {
    setState(s => ({ ...s, isUploading: true, error: null }))

    try {
      const result = await scoreUpload(state.userId, {
        source_type: 'pdf',
        content: content,
      })

      const regionScores = aggregateToRegions(result.profile_after)
      setState(s => ({
        ...s,
        profile: s.profile ? { ...s.profile, category_scores: result.profile_after } : null,
        regionScores,
        isUploading: false,
        lastUpdate: result,
      }))

      refreshProfile()
      return result
    } catch (err) {
      setState(s => ({
        ...s,
        isUploading: false,
        error: err instanceof Error ? err.message : 'Failed to analyze PDF',
      }))
      throw err
    }
  }, [state.userId, refreshProfile])

  // Clear error state
  const clearError = useCallback(() => {
    setState(s => ({ ...s, error: null }))
  }, [])

  // Reset session — wipe all scores and uploads
  const resetSession = useCallback(async () => {
    if (!state.userId) return

    setState(s => ({ ...s, isLoading: true, error: null }))
    try {
      const profile = await resetProfile(state.userId)
      const regionScores = aggregateToRegions(profile.category_scores)

      setState(s => ({
        ...s,
        profile,
        regionScores,
        uploads: [],
        isLoading: false,
        lastUpdate: null,
        error: null,
      }))
    } catch (err) {
      setState(s => ({
        ...s,
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to reset session',
      }))
    }
  }, [state.userId])

  const value = useMemo(() => ({
    ...state,
    refreshProfile,
    uploadGitHubRepo,
    uploadPdf,
    resetSession,
    clearError,
  }), [state, refreshProfile, uploadGitHubRepo, uploadPdf, resetSession, clearError])

  return (
    <ProfileContext.Provider value={value}>
      {children}
    </ProfileContext.Provider>
  )
}

// ── Hook ──────────────────────────────────────────────────

export function useProfile() {
  const context = useContext(ProfileContext)
  if (!context) {
    throw new Error('useProfile must be used within a ProfileProvider')
  }
  return context
}
