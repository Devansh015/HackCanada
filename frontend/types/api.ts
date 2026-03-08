/**
 * TypeScript interfaces matching backend Pydantic models
 * from backend/profile_scoring/models.py
 */

// User profile with 50 category scores
export interface UserProfile {
  user_id: string
  category_scores: Record<string, number>  // category_key → 0.0-1.0
  upload_count: number
  created_at: string
  updated_at: string
}

// API response wrappers
export interface ProfileResponse {
  success: boolean
  profile: UserProfile
}

export interface TopCategoriesResponse {
  success: boolean
  top: { category: string; score: number }[]
  upload_count: number
}

export interface HistoryResponse {
  success: boolean
  count: number
  history: UploadScoreSnapshot[]
}

// Result from Gemini scoring a single upload
export interface GeminiScoringResult {
  scores: Record<string, number>
  explanations: Record<string, string>
  summary: string
}

// Snapshot of a single upload's impact
export interface UploadScoreSnapshot {
  upload_id: string
  user_id: string
  source_type: 'github_repo' | 'pdf' | 'text_prompt'
  content_preview: string
  upload_scores: Record<string, number>
  score_deltas: Record<string, number>
  profile_after: Record<string, number>
  timestamp?: string
}

// Response from score-upload endpoint
export interface ScoreUploadResponse {
  success: boolean
  summary: ProfileUpdateSummary
  gemini_scores: Record<string, number> | null
  error: string | null
}

export interface ProfileUpdateSummary {
  user_id: string
  upload_id: string
  source_type: string
  categories_increased: { category: string; delta: number }[]
  categories_unchanged: string[]
  top_influenced: { category: string; delta: number }[]
  profile_before: Record<string, number>
  profile_after: Record<string, number>
  gemini_summary: string
  upload_count: number
}

// Request body for score-upload
export interface ScoreUploadRequest {
  source_type: 'github_repo' | 'pdf' | 'text_prompt'
  content: string
  gemini_api_key?: string
}

// API error response
export interface ApiError {
  detail: string
}
