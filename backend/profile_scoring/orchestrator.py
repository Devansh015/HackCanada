"""
Orchestrator – single entry-point for scoring uploads and managing profiles.

Delegates to:
  - gemini_scorer   → content → category scores
  - profile_manager → merge, persist, summarise
  - GitHubProcessor → fetch real repo content from GitHub API
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .gemini_scorer import score_content_with_gemini
from .profile_manager import (
    get_user_profile,
    initialize_user_profile,
    update_user_profile_from_upload,
    get_profile_change_summary,
)

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
#  Public helpers (re-exported via __init__)
# ────────────────────────────────────────────────────────────

# These two are re-exported so that router.py / __init__.py can import them
# directly from the orchestrator module.
initialize_user_profile = initialize_user_profile
get_user_profile = get_user_profile
get_profile_change_summary = get_profile_change_summary


# ────────────────────────────────────────────────────────────
#  Main entry-point
# ────────────────────────────────────────────────────────────

def update_profile_from_upload(
    user_id: str,
    source_type: str,
    content: str,
    gemini_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Score *content* and merge the result into the user's profile.

    For ``source_type == "github_repo"`` the raw *content* is expected to
    be a GitHub URL.  We hand it to ``GitHubProcessor`` so that the real
    repository text (README, description, languages, topics) is fetched
    via the GitHub API before scoring — instead of scoring the bare URL.

    Returns
    -------
    dict with keys ``success``, ``summary`` (or ``error``).
    """

    # ── Basic validation ───────────────────────────────────
    if not content or len(content.strip()) < 10:
        return {
            "success": False,
            "error": "Content too short to analyse.",
            "summary": None,
        }

    # ── GitHub repo: fetch real content ────────────────────
    scoring_content = content
    if source_type == "github_repo":
        try:
            from backend.ingestion.github_processor import GitHubProcessor

            processor = GitHubProcessor()
            result = processor.process(content, user_id)

            extracted = (result.get("content") or "").strip()
            if extracted:
                scoring_content = extracted
                logger.info(
                    "GitHubProcessor returned %d chars for %s",
                    len(scoring_content),
                    content,
                )
            else:
                # GitHub API may have failed / rate-limited – fall back to
                # scoring the raw URL string so the pipeline doesn't break.
                logger.warning(
                    "GitHubProcessor returned empty content for %s – "
                    "falling back to raw URL",
                    content,
                )
        except Exception as exc:
            logger.error("GitHubProcessor failed: %s – scoring raw URL", exc)

    # ── Score with Gemini (or keyword fallback) ────────────
    gemini_result = score_content_with_gemini(
        scoring_content,
        source_type=source_type,
        api_key=gemini_api_key,
    )

    # ── Merge into the user's profile ──────────────────────
    try:
        summary = update_user_profile_from_upload(
            user_id=user_id,
            source_type=source_type,
            content=content,
            gemini_result=gemini_result,
        )
        return {
            "success": True,
            "summary": summary.model_dump(),
            "gemini_scores": gemini_result.scores,
            "error": None,
        }
    except Exception as exc:
        logger.error("Profile update failed: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "summary": None,
        }
