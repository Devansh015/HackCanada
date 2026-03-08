"""
Gemini-based content → category scoring service.

Takes arbitrary text (from PDFs, GitHub readmes, text prompts, etc.) and
asks Google Gemini to estimate relevance to each technical category.

Returns a GeminiScoringResult with structured scores 0-1 and brief
explanations for the strongest categories.

Environment
-----------
  GEMINI_API_KEY  – required (Google AI Studio or Vertex key)
  GEMINI_MODEL    – optional, defaults to "gemini-2.0-flash"
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, Optional

from .categories import CATEGORY_KEYS, CATEGORY_MAP, zero_scores
from .models import GeminiScoringResult

# Load .env from project root
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────
#  Configuration
# ────────────────────────────────────────────────────────────

# Prefer the Google Cloud Console key (billing-enabled)
GEMINI_API_KEY: str = os.getenv("GOOGLE_CLOUD_CONSOLE_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
MAX_CONTENT_CHARS: int = 6_000    # Trimmed from 12K → 6K to halve input tokens

# ── Token tracking ────────────────────────────────────────
total_gemini_tokens: int = 0       # Cumulative tokens across all calls this run
total_gemini_calls: int = 0        # Number of actual API calls made

# ── Response cache (hash → GeminiScoringResult) ───────────
_score_cache: Dict[str, GeminiScoringResult] = {}

def get_token_stats() -> Dict[str, int]:
    """Return cumulative token/call stats for the current process."""
    return {"total_tokens": total_gemini_tokens, "total_calls": total_gemini_calls}

def reset_token_stats() -> None:
    """Reset counters (useful at start of a profiling run)."""
    global total_gemini_tokens, total_gemini_calls
    total_gemini_tokens = 0
    total_gemini_calls = 0
    _score_cache.clear()


# ────────────────────────────────────────────────────────────
#  Prompt template
# ────────────────────────────────────────────────────────────

# ────────────────────────────────────────────────────────────
#  Prompt template  (compact — saves ~60% input tokens)
# ────────────────────────────────────────────────────────────

# Just the keys, no labels — Gemini knows what they mean
_CATEGORY_KEYS_STR = ", ".join(CATEGORY_KEYS)

SCORING_PROMPT_TEMPLATE = """Score this content's relevance to CS categories.
Categories: {categories}

Scale: 0.0=none, 0.3=mentioned, 0.6=demonstrated, 1.0=expert.
Only include categories scoring >0. Return compact JSON:
{{"s":{{"key":float,...}}}}

Content:
{content}"""


# ────────────────────────────────────────────────────────────
#  Public API
# ────────────────────────────────────────────────────────────

def score_content_with_gemini(
    content: str,
    source_type: str = "text_prompt",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> GeminiScoringResult:
    """
    Send *content* to Gemini and return structured category scores.

    Falls back to a keyword-based heuristic if Gemini is unavailable
    (missing key, network error, etc.) so the pipeline never hard-fails.

    Parameters
    ----------
    content      : The extracted text from the upload.
    source_type  : "text_prompt", "github_repo", or "pdf".
    api_key      : Override for GEMINI_API_KEY env var.
    model        : Override for GEMINI_MODEL env var.

    Returns
    -------
    GeminiScoringResult
    """
    key = api_key or GEMINI_API_KEY
    mdl = model or GEMINI_MODEL

    if not key:
        logger.warning("GEMINI_API_KEY not set – falling back to keyword scorer")
        return _keyword_fallback(content)

    if not content or len(content.strip()) < 10:
        logger.warning("Content too short for scoring – returning zeros")
        return GeminiScoringResult(
            scores=zero_scores(),
            overall_summary="Content was empty or too short to analyse.",
            model_used=mdl,
        )

    trimmed = content[:MAX_CONTENT_CHARS]

    # ── Cache check (avoid re-scoring identical content) ────
    content_hash = hashlib.md5(trimmed.encode()).hexdigest()
    if content_hash in _score_cache:
        logger.info("Cache hit – skipping Gemini call")
        return _score_cache[content_hash]

    prompt = SCORING_PROMPT_TEMPLATE.format(
        categories=_CATEGORY_KEYS_STR,
        content=trimmed,
    )

    try:
        global total_gemini_tokens, total_gemini_calls
        raw_text, token_count = _call_gemini(prompt, key, mdl)
        total_gemini_tokens += token_count
        total_gemini_calls += 1
        result = _parse_gemini_response(raw_text)
        result.model_used = mdl
        result.token_count = token_count
        _score_cache[content_hash] = result
        return result

    except Exception as exc:
        logger.error(f"Gemini scoring failed: {exc} – falling back to keywords")
        return _keyword_fallback(content)


# ────────────────────────────────────────────────────────────
#  Gemini API call (google-genai SDK)
# ────────────────────────────────────────────────────────────

def _call_gemini(prompt: str, api_key: str, model: str) -> tuple[str, int]:
    """Call the Gemini API and return (response_text, token_count)."""
    try:
        from google import genai
    except ImportError:
        raise ImportError(
            "google-genai is required for Gemini scoring. "
            "Install with: pip install google-genai"
        )

    client = genai.Client(api_key=api_key)

    # Build config — disable thinking for 2.5 models (saves ~5-8s per call)
    config_kwargs = dict(
        temperature=0.0,
        max_output_tokens=2048,
        response_mime_type="application/json",
    )

    # Gemini 2.5 models support thinking budget — set to 0 to skip thinking
    if "2.5" in model:
        try:
            config_kwargs["thinking_config"] = genai.types.ThinkingConfig(
                thinking_budget=0
            )
        except (AttributeError, TypeError):
            pass  # Older SDK versions may not support this

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai.types.GenerateContentConfig(**config_kwargs),
    )

    text = response.text or ""
    tokens = 0
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        tokens = getattr(response.usage_metadata, "total_token_count", 0)

    return text, tokens


# ────────────────────────────────────────────────────────────
#  Response parsing
# ────────────────────────────────────────────────────────────

def _repair_truncated_json(raw: str) -> Optional[dict]:
    """
    Attempt to recover scores from truncated JSON like:
      {"s":{"git":1.0,"testing":0.6,"oop":0
    Strategy: find all complete "key":value pairs, ignore the rest.
    """
    # Try progressively stripping trailing chars and closing brackets
    for trim in range(min(len(raw), 60)):
        candidate = raw[: len(raw) - trim]
        # Remove any trailing partial key or value
        candidate = re.sub(r',\s*"[^"]*$', "", candidate)   # trailing partial key
        candidate = re.sub(r',\s*$', "", candidate)           # trailing comma

        # Count open/close braces and brackets, close what's needed
        opens = candidate.count("{") - candidate.count("}")
        candidate += "}" * max(opens, 0)
        opens_b = candidate.count("[") - candidate.count("]")
        candidate += "]" * max(opens_b, 0)

        try:
            data = json.loads(candidate)
            return data
        except json.JSONDecodeError:
            continue
    return None

def _parse_gemini_response(raw: str) -> GeminiScoringResult:
    """Parse the JSON Gemini returns into a GeminiScoringResult."""
    # Strip markdown code fences if Gemini wraps anyway
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Gemini 2.5 often truncates JSON — try to repair it
        data = _repair_truncated_json(cleaned)
        if data is None:
            logger.error(f"Gemini returned unrepairable JSON\nRaw: {raw[:300]}")
            return GeminiScoringResult(
                scores=zero_scores(),
                overall_summary="Failed to parse Gemini response.",
            )
        logger.info(f"Repaired truncated JSON — recovered {len(data.get('s', data.get('scores', {})))} scores")

    # Support both compact {"s": {...}} and legacy {"scores": {...}} formats
    raw_scores = data.get("s", data.get("scores", {}))
    scores: Dict[str, float] = {}
    for key in CATEGORY_KEYS:
        val = raw_scores.get(key, 0.0)
        try:
            scores[key] = max(0.0, min(1.0, float(val)))
        except (TypeError, ValueError):
            scores[key] = 0.0

    explanations = {
        k: str(v) for k, v in data.get("explanations", data.get("e", {})).items()
        if k in CATEGORY_KEYS
    }

    return GeminiScoringResult(
        scores=scores,
        explanations=explanations,
        overall_summary=data.get("overall_summary", data.get("sum", "")),
    )


# ────────────────────────────────────────────────────────────
#  Keyword-based fallback (no Gemini key)
# ────────────────────────────────────────────────────────────

_KEYWORD_MAP: Dict[str, list[str]] = {
    "variables":           ["variable", "var ", "let ", "const ", "assign"],
    "functions":           ["function", "def ", "lambda", "callback", "return "],
    "control_flow":        ["if ", "else", "elif", "switch", "while", "for ", "loop"],
    "recursion":           ["recursion", "recursive", "base case", "call stack"],
    "oop":                 ["object-oriented", "oop", "object oriented"],
    "classes":             ["class ", "class(", "classmethod", "staticmethod"],
    "objects":             ["object", "instance", "instantiate"],
    "inheritance":         ["inherit", "extends", "super(", "subclass", "parent class"],
    "polymorphism":        ["polymorphism", "overriding", "overloading", "duck typing"],
    "encapsulation":       ["encapsulation", "private", "protected", "getter", "setter"],
    "abstraction":         ["abstraction", "abstract class", "interface", "abc"],
    "methods":             ["method", "self.", "this."],
    "constructors":        ["constructor", "__init__", "super()", "new "],
    "data_structures":     ["data structure", "collection", "container"],
    "arrays":              ["array", "list", "vector", "slice"],
    "linked_lists":        ["linked list", "node.next", "singly linked", "doubly linked"],
    "stacks":              ["stack", "push", "pop", "lifo"],
    "queues":              ["queue", "enqueue", "dequeue", "fifo", "bfs"],
    "trees":               ["tree", "binary tree", "bst", "traversal", "root node"],
    "graphs":              ["graph", "vertex", "edge", "adjacency", "dfs", "bfs"],
    "hash_tables":         ["hash", "hashmap", "dictionary", "dict", "hashtable"],
    "algorithms":          ["algorithm", "complexity", "big-o", "optimal"],
    "sorting":             ["sort", "quicksort", "mergesort", "bubblesort", "heapsort"],
    "searching":           ["search", "binary search", "linear search", "lookup"],
    "dynamic_programming": ["dynamic programming", "memoization", "tabulation", "dp "],
    "time_complexity":     ["time complexity", "big o", "O(n)", "O(log", "runtime"],
    "space_complexity":    ["space complexity", "memory usage", "auxiliary space"],
    "databases":           ["database", "db ", "rdbms", "nosql", "mongodb", "postgres"],
    "sql":                 ["sql", "select ", "join ", "query", "insert "],
    "indexing":            ["index", "b-tree", "indexing", "primary key"],
    "apis":                ["api", "rest", "endpoint", "request", "response", "graphql"],
    "operating_systems":   ["operating system", "os ", "kernel", "process", "thread"],
    "memory_management":   ["memory", "heap", "stack memory", "garbage collect", "malloc"],
    "concurrency":         ["concurrency", "parallel", "mutex", "semaphore", "async"],
    "networking":          ["network", "tcp", "udp", "http", "socket", "ip "],
    "git":                 ["git", "commit", "branch", "merge", "pull request", "repo"],
    "testing":             ["test", "unittest", "pytest", "assert", "mock", "tdd"],
}


def _keyword_fallback(content: str) -> GeminiScoringResult:
    """Simple keyword-frequency scorer used when Gemini is unavailable."""
    lower = content.lower()
    word_count = max(len(lower.split()), 1)
    scores: Dict[str, float] = {}

    for cat, keywords in _KEYWORD_MAP.items():
        hits = sum(lower.count(kw) for kw in keywords)
        # Normalise: rough density → clamped 0-1
        raw = min(hits / (word_count * 0.02), 1.0)
        scores[cat] = round(raw, 4)

    # Fill any missing
    for key in CATEGORY_KEYS:
        scores.setdefault(key, 0.0)

    return GeminiScoringResult(
        scores=scores,
        overall_summary="Scored via keyword fallback (Gemini unavailable).",
        model_used="keyword_fallback",
    )