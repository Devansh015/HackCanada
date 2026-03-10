"""
Chatbot service – Gemini-powered conversational advisor.

Uses the user's profile scores + category metadata to provide
personalised insights, learning advice, project suggestions,
and skill-gap analysis through natural conversation.

Environment
-----------
  GOOGLE_CLOUD_CONSOLE_API_KEY – same key as the scorer
  GEMINI_MODEL                 – defaults to "gemini-2.0-flash"
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from backend.profile_scoring.categories import (
    CATEGORY_GROUPS,
    CATEGORY_KEYS,
    CATEGORY_MAP,
)
from backend.profile_scoring.models import UserProfile
from backend.profile_scoring.profile_manager import (
    get_upload_history,
    get_user_profile,
)

from .models import (
    ChatMessage,
    ChatResponse,
    InsightItem,
    InsightsResponse,
)

# Load .env from project root
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
except ImportError:
    pass

logger = logging.getLogger(__name__)

GEMINI_API_KEY: str = os.getenv("GOOGLE_CLOUD_CONSOLE_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


# ────────────────────────────────────────────────────────────
#  Helpers
# ────────────────────────────────────────────────────────────

# ── Proficiency tiers ──────────────────────────────────────
#  Maps a 0-1 score to a human-readable tier label.
#  These tiers are injected into the system prompt so Gemini
#  uses meaningful language instead of raw decimals.

_TIERS = [
    (0.00, "Unassessed"),       # exactly 0 — no evidence yet
    (0.15, "Novice"),           # 0.01 – 0.15  — minimal exposure
    (0.35, "Beginner"),         # 0.16 – 0.35  — some familiarity
    (0.55, "Intermediate"),     # 0.36 – 0.55  — working knowledge
    (0.75, "Proficient"),       # 0.56 – 0.75  — solid competence
    (0.90, "Advanced"),         # 0.76 – 0.90  — strong expertise
    (1.01, "Expert"),           # 0.91 – 1.00  — exceptional mastery
]


def _tier_label(score: float) -> str:
    """Return the qualitative tier name for a numeric score."""
    if score == 0.0:
        return "Unassessed"
    for threshold, label in _TIERS:
        if score <= threshold:
            return label
    return "Expert"


def _profile_snapshot(profile: UserProfile) -> str:
    """Build a concise textual summary of a user's profile for the prompt.

    Only tier labels are included – numeric scores are deliberately
    omitted so Gemini never quotes them back to the user.
    """
    lines: List[str] = []

    # Group scores by region
    groups: Dict[str, List[tuple]] = {}
    for key in CATEGORY_KEYS:
        group = CATEGORY_GROUPS[key]
        score = profile.category_scores.get(key, 0.0)
        tier = _tier_label(score)
        groups.setdefault(group, []).append(
            (CATEGORY_MAP[key], tier)
        )

    for group_name, cats in groups.items():
        avg = sum(
            profile.category_scores.get(k, 0.0)
            for k in CATEGORY_KEYS if CATEGORY_GROUPS[k] == group_name
        ) / max(len(cats), 1)
        region_tier = _tier_label(avg)
        cat_details = ", ".join(
            f"{name}: {tier}" for name, tier in cats
        )
        lines.append(
            f"  {group_name} (overall {region_tier}): {cat_details}"
        )

    top = profile.get_top_categories(5)
    top_str = ", ".join(
        f"{t['category']}: {_tier_label(t['score'])}"
        for t in top
    )

    return (
        f"Upload count: {profile.upload_count}\n"
        f"Top-5: {top_str}\n"
        f"Skills by region:\n" + "\n".join(lines)
    )


def _upload_history_summary(user_id: str) -> str:
    """Build a short summary of the user's uploaded projects/content."""
    history = get_upload_history(user_id)
    if not history:
        return "No uploads yet."

    lines: List[str] = []
    for i, snap in enumerate(history[-10:], 1):  # last 10 uploads
        source = snap.source_type.replace("_", " ").title()
        preview = snap.content_preview.strip()[:150]
        # Find top categories this upload contributed to
        top_cats = sorted(
            snap.upload_scores.items(), key=lambda kv: kv[1], reverse=True
        )[:3]
        cat_str = ", ".join(
            f"{CATEGORY_MAP.get(k, k)}: {_tier_label(v)}"
            for k, v in top_cats if v > 0.0
        )
        line = f"  {i}. [{source}] {preview}"
        if cat_str:
            line += f" — strongest in: {cat_str}"
        lines.append(line)

    return "\n".join(lines)


def _build_system_prompt(profile: UserProfile) -> str:
    """Construct the system prompt that grounds the chatbot in the user's data."""
    snapshot = _profile_snapshot(profile)
    uploads = _upload_history_summary(profile.user_id)

    return f"""You are Cortex, a friendly and concise CS learning advisor.

You know the user's Knowledge Map which rates their skills using these
levels: Unassessed, Novice, Beginner, Intermediate, Proficient, Advanced,
Expert.

─── CURRENT PROFILE ───
{snapshot}
────────────────────────

─── UPLOADED PROJECTS / CONTENT ───
{uploads}
────────────────────────────────────

Rules (follow strictly):
1. Keep every reply to 3-4 sentences max. Be direct and helpful.
2. NEVER mention or reveal any numeric score, percentage, or number
   between 0 and 1. Only use the level names (Novice, Beginner, etc.).
3. NEVER use XML-style tags, HTML tags, or any bracket-based markup
   in your replies. Plain text and simple markdown only.
4. Be encouraging – highlight strengths before gaps.
5. Use the level names naturally, e.g. "You're at an Intermediate level
   in Sorting" – never say "your score is 0.5".
6. For Unassessed categories, say the skill hasn't been evaluated yet,
   not that it's a weakness.
7. When the user has few uploads, suggest uploading more content.
8. If asked about something outside CS, gently redirect.
9. When relevant, reference the user's actual projects or uploads by
   name/description to make advice concrete and personal.
"""


# ────────────────────────────────────────────────────────────
#  Chat
# ────────────────────────────────────────────────────────────

def chat_with_profile(
    user_id: str,
    message: str,
    conversation_history: Optional[List[ChatMessage]] = None,
) -> ChatResponse:
    """
    Send a user message to Gemini, grounded in the user's profile.

    Parameters
    ----------
    user_id : str
        The profile to load context from.
    message : str
        The latest user message.
    conversation_history : list[ChatMessage], optional
        Prior turns for multi-turn context.

    Returns
    -------
    ChatResponse with reply text and follow-up suggestions.
    """
    from google import genai

    profile = get_user_profile(user_id)
    if profile is None:
        return ChatResponse(
            reply="I don't have a profile for you yet. Please upload some content first so I can learn about your skills!",
            suggestions=[
                "How do I upload a GitHub repo?",
                "What kind of content can I upload?",
            ],
        )

    system_prompt = _build_system_prompt(profile)

    # Build Gemini contents list (multi-turn)
    contents: list = []
    if conversation_history:
        for msg in conversation_history[-10:]:  # keep last 10 turns
            role = "user" if msg.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg.content}]})

    # Append the new user message
    contents.append({"role": "user", "parts": [{"text": message}]})

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config={
                "system_instruction": system_prompt,
                "temperature": 0.7,
                "max_output_tokens": 800,
            },
        )
        reply_text = response.text or "I'm sorry, I couldn't generate a response."
    except Exception as exc:
        logger.error("Gemini chat error: %s", exc)
        reply_text = (
            "I'm having trouble connecting to my AI backend right now. "
            "Please try again in a moment."
        )

    # Generate follow-up suggestions based on context
    suggestions = _generate_suggestions(profile, message)

    return ChatResponse(reply=reply_text, suggestions=suggestions)


def _generate_suggestions(profile: UserProfile, last_message: str) -> List[str]:
    """Return 2-3 contextual follow-up suggestions."""
    suggestions: List[str] = []

    top = profile.get_top_categories(3)
    top_names = [t["category"] for t in top]

    # Always offer these if the profile is thin
    if profile.upload_count < 3:
        suggestions.append("What should I upload next to improve my profile?")

    # Suggest exploring strengths
    if top and top[0]["score"] > 0.1:
        suggestions.append(f"What projects can I build with my {CATEGORY_MAP.get(top_names[0], top_names[0])} skills?")

    # Suggest growth areas
    weak = sorted(
        profile.category_scores.items(), key=lambda kv: kv[1]
    )
    nonzero_weak = [(k, v) for k, v in weak if v > 0.0]
    if nonzero_weak:
        weakest_name = CATEGORY_MAP.get(nonzero_weak[0][0], nonzero_weak[0][0])
        suggestions.append(f"How can I improve my {weakest_name} skills?")
    else:
        suggestions.append("What are the most important CS topics to learn first?")

    return suggestions[:3]


# ────────────────────────────────────────────────────────────
#  Auto-generated Insights
# ────────────────────────────────────────────────────────────

def generate_insights(user_id: str) -> InsightsResponse:
    """
    Analyse the user's profile and return structured insights
    without requiring a chat message.
    """
    profile = get_user_profile(user_id)
    if profile is None:
        return InsightsResponse(
            summary="No profile found. Upload some content to get started!"
        )

    scores = profile.category_scores

    # ── Strengths (top categories with score > 0.1) ────────
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    strengths: List[InsightItem] = []
    for key, score in ranked:
        if score < 0.1 or len(strengths) >= 5:
            break
        tier = _tier_label(score)
        strengths.append(InsightItem(
            category=CATEGORY_GROUPS.get(key, "General"),
            title=CATEGORY_MAP.get(key, key),
            detail=f"{tier} ({score:.2f}) — you've shown solid evidence in this area.",
            score=score,
        ))

    # ── Growth areas (lowest non-zero or zero with related strengths) ──
    growth_areas: List[InsightItem] = []
    # Find groups where user has *some* evidence but gaps remain
    group_scores: Dict[str, List[float]] = {}
    for key in CATEGORY_KEYS:
        g = CATEGORY_GROUPS[key]
        group_scores.setdefault(g, []).append(scores.get(key, 0.0))

    for g, g_scores in group_scores.items():
        avg = sum(g_scores) / len(g_scores) if g_scores else 0.0
        tier = _tier_label(avg)
        if 0.0 < avg < 0.4:
            growth_areas.append(InsightItem(
                category=g,
                title=f"Grow your {g} skills",
                detail=(
                    f"Currently at {tier} level (avg {avg:.2f}). "
                    "Consider focused practice or a project in this area."
                ),
                score=round(avg, 3),
            ))

    # ── Learning paths ────────────────────────────────────
    learning_paths: List[str] = []
    # Suggest path based on weakest group that has any evidence
    sorted_groups = sorted(
        ((g, sum(s) / len(s)) for g, s in group_scores.items()),
        key=lambda x: x[1],
    )
    for g_name, g_avg in sorted_groups[:3]:
        tier = _tier_label(g_avg)
        if g_avg < 0.3:
            learning_paths.append(
                f"📚 {g_name} ({tier}): Start with fundamentals, then build a small project."
            )
        elif g_avg < 0.6:
            learning_paths.append(
                f"🚀 {g_name} ({tier}): You have a foundation — try intermediate challenges or contribute to open source."
            )

    if not learning_paths:
        learning_paths.append(
            "🎯 Upload more content to unlock personalised learning paths!"
        )

    # ── Summary ────────────────────────────────────────────
    strength_names = [s.title for s in strengths[:3]]
    summary = (
        f"Based on {profile.upload_count} upload(s), "
        f"your strongest areas are: {', '.join(strength_names) if strength_names else 'still forming'}. "
        f"Keep uploading repos and documents to refine your Knowledge Map!"
    )

    return InsightsResponse(
        strengths=strengths,
        growth_areas=growth_areas,
        learning_paths=learning_paths,
        summary=summary,
    )
