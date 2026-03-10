/**
 * API client for Cortex backend
 */

import type {
  UserProfile,
  ProfileResponse,
  ProfileUpdateSummary,
  HistoryResponse,
  ScoreUploadRequest,
  UploadScoreSnapshot,
  ChatMessage,
  ChatResponse,
  InsightsResponse,
} from '@/types/api'

const API_ROOT = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080').replace(/\/$/, '')
const API_BASE = `${API_ROOT}/api`

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new ApiError(response.status, error.detail || `HTTP ${response.status}`)
  }
  return response.json()
}

/**
 * Initialize a new user profile with zero scores
 */
export async function initProfile(userId: string): Promise<UserProfile> {
  const response = await fetch(`${API_BASE}/profile/${userId}/init`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  const data = await handleResponse<ProfileResponse>(response)
  return data.profile
}

/**
 * Get current user profile with all category scores
 */
export async function getProfile(userId: string): Promise<UserProfile> {
  const response = await fetch(`${API_BASE}/profile/${userId}`)
  const data = await handleResponse<ProfileResponse>(response)
  return data.profile
}

/**
 * Get or create user profile
 */
export async function getOrCreateProfile(userId: string): Promise<UserProfile> {
  try {
    return await getProfile(userId)
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return await initProfile(userId)
    }
    throw error
  }
}

/**
 * Get top N categories for a user
 */
export async function getTopCategories(
  userId: string,
  limit: number = 10
): Promise<{ category: string; score: number }[]> {
  const response = await fetch(`${API_BASE}/profile/${userId}/top?limit=${limit}`)
  const data = await handleResponse<{
    success: boolean
    top: { category: string; score: number }[]
    upload_count: number
  }>(response)
  return data.top
}

/**
 * Score an upload (GitHub repo, PDF, or text) and update profile
 */
export async function scoreUpload(
  userId: string,
  request: ScoreUploadRequest
): Promise<ProfileUpdateSummary> {
  const response = await fetch(`${API_BASE}/profile/${userId}/score-upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  const data = await handleResponse<{
    success: boolean
    summary: ProfileUpdateSummary
    error: string | null
  }>(response)

  if (!data.success || !data.summary) {
    throw new ApiError(422, data.error || 'Scoring failed')
  }

  return data.summary
}

/**
 * Get upload history for a user
 */
export async function getUploadHistory(userId: string): Promise<UploadScoreSnapshot[]> {
  const response = await fetch(`${API_BASE}/profile/${userId}/history`)
  const data = await handleResponse<HistoryResponse>(response)
  return data.history
}

/**
 * Reset user profile to zero scores
 */
export async function resetProfile(userId: string): Promise<UserProfile> {
  const response = await fetch(`${API_BASE}/profile/${userId}/reset`, {
    method: 'POST',
  })
  const data = await handleResponse<ProfileResponse>(response)
  return data.profile
}

/**
 * Parse GitHub URL to extract content for scoring
 */
export function parseGitHubUrl(url: string): { owner: string; repo: string } | null {
  const match = url.match(/github\.com\/([^\/]+)\/([^\/]+)/)
  if (!match) return null
  return { owner: match[1], repo: match[2].replace(/\.git$/, '') }
}

/**
 * Generate a UUID for anonymous user identification
 */
export function generateUserId(): string {
  return 'user_' + crypto.randomUUID()
}

/**
 * Get or create user ID from localStorage
 */
export function getStoredUserId(): string {
  if (typeof window === 'undefined') return generateUserId()

  const stored = localStorage.getItem('cortex_user_id')
  if (stored) return stored

  const newId = generateUserId()
  localStorage.setItem('cortex_user_id', newId)
  return newId
}

/**
 * Send a chat message and get AI response
 */
export async function sendChatMessage(
  userId: string,
  message: string,
  conversationHistory: ChatMessage[] = []
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat/${userId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, conversation_history: conversationHistory }),
  })
  return handleResponse<ChatResponse>(response)
}

/**
 * Get AI-generated insights about the user's profile
 */
export async function getInsights(userId: string): Promise<InsightsResponse> {
  const response = await fetch(`${API_BASE}/chat/${userId}/insights`)
  return handleResponse<InsightsResponse>(response)
}