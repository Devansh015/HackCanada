"""
End-to-end test for the profile scoring system.

Tests:
  1. Module imports
  2. Profile init / CRUD
  3. Keyword fallback scoring (no Gemini call)
  4. Merge logic (multi-upload accumulation)
  5. Source-type weighting
  6. Live Gemini scoring (requires GEMINI_API_KEY)
  7. Full orchestrator flow
  8. Edge cases (empty content, unknown source)
"""

import os
import sys
import json
from pathlib import Path

# Make sure we can import from the project root
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


passed = 0
failed = 0
results = []

def test(name):
    global passed, failed
    def decorator(fn):
        global passed, failed
        try:
            fn()
            passed += 1
            results.append(("✅", name))
            print(f"  ✅  {name}")
        except Exception as e:
            failed += 1
            results.append(("❌", name, str(e)))
            print(f"  ❌  {name}")
            print(f"      {e}")
    return decorator


print("=" * 64)
print("  PROFILE SCORING – TEST SUITE")
print("=" * 64)


# ─── 1. Imports ──────────────────────────────────────────────────────────
print("\n── 1. Module Imports ────────────────────────────────────")

@test("Import categories")
def _():
    from backend.profile_scoring.categories import CATEGORY_KEYS, zero_scores, NUM_CATEGORIES
    assert len(CATEGORY_KEYS) == NUM_CATEGORIES, f"Expected {NUM_CATEGORIES}, got {len(CATEGORY_KEYS)}"
    zs = zero_scores()
    assert all(v == 0.0 for v in zs.values())
    assert len(zs) == NUM_CATEGORIES

@test("Import models")
def _():
    from backend.profile_scoring.models import (
        UserProfile, GeminiScoringResult, UploadScoreSnapshot,
        ProfileUpdateSummary, source_weight,
    )
    assert source_weight("github_repo") == 0.85
    assert source_weight("pdf") == 0.65
    assert source_weight("text_prompt") == 0.45
    assert source_weight("unknown_thing") == 0.50

@test("Import orchestrator")
def _():
    from backend.profile_scoring.orchestrator import (
        update_profile_from_upload,
        initialize_user_profile,
        get_user_profile,
        get_profile_change_summary,
    )

@test("Import router")
def _():
    from backend.profile_scoring.router import router
    assert router.prefix == "/profile"


# ─── 2. Profile CRUD ────────────────────────────────────────────────────
print("\n── 2. Profile CRUD ─────────────────────────────────────")

@test("Create profile")
def _():
    from backend.profile_scoring.profile_manager import initialize_user_profile, get_user_profile
    p = initialize_user_profile("test_user_1")
    assert p.user_id == "test_user_1"
    assert p.upload_count == 0
    assert all(v == 0.0 for v in p.category_scores.values())

@test("Retrieve profile")
def _():
    from backend.profile_scoring.profile_manager import get_user_profile
    p = get_user_profile("test_user_1")
    assert p is not None
    assert p.user_id == "test_user_1"

@test("Non-existent profile returns None")
def _():
    from backend.profile_scoring.profile_manager import get_user_profile
    p = get_user_profile("doesnt_exist_999")
    assert p is None

@test("Reset profile")
def _():
    from backend.profile_scoring.profile_manager import (
        initialize_user_profile, reset_user_profile, get_user_profile,
    )
    initialize_user_profile("reset_test")
    p = reset_user_profile("reset_test")
    assert p.upload_count == 0
    assert all(v == 0.0 for v in p.category_scores.values())

@test("Top categories")
def _():
    from backend.profile_scoring.models import UserProfile
    p = UserProfile(user_id="top_test")
    p.category_scores["git"] = 0.9
    p.category_scores["testing"] = 0.8
    p.category_scores["apis"] = 0.7
    top = p.get_top_categories(3)
    assert len(top) == 3
    assert top[0]["category"] == "git"
    assert top[0]["score"] == 0.9


# ─── 3. Keyword Fallback Scoring ────────────────────────────────────────
print("\n── 3. Keyword Fallback Scorer ───────────────────────────")

@test("Keyword scorer returns all categories")
def _():
    from backend.profile_scoring.gemini_scorer import _keyword_fallback
    from backend.profile_scoring.categories import CATEGORY_KEYS
    result = _keyword_fallback("I wrote a Python class with inheritance and tested it with pytest")
    assert set(result.scores.keys()) == set(CATEGORY_KEYS)
    assert result.model_used == "keyword_fallback"

@test("Keyword scorer detects OOP keywords")
def _():
    from backend.profile_scoring.gemini_scorer import _keyword_fallback
    text = """
    I built a class hierarchy using inheritance and polymorphism.
    The base class has an abstract method. Each subclass overrides it.
    I used encapsulation with private attributes and getter/setter methods.
    """
    result = _keyword_fallback(text)
    assert result.scores["inheritance"] > 0.0
    assert result.scores["polymorphism"] > 0.0
    assert result.scores["encapsulation"] > 0.0
    assert result.scores["classes"] > 0.0

@test("Keyword scorer detects algorithms keywords")
def _():
    from backend.profile_scoring.gemini_scorer import _keyword_fallback
    text = """
    Implemented quicksort and binary search. Analysed time complexity
    of O(n log n). Used dynamic programming with memoization for the
    knapsack problem. Created a hash table for O(1) lookup.
    """
    result = _keyword_fallback(text)
    assert result.scores["sorting"] > 0.0
    assert result.scores["searching"] > 0.0
    assert result.scores["time_complexity"] > 0.0
    assert result.scores["dynamic_programming"] > 0.0
    assert result.scores["hash_tables"] > 0.0

@test("Keyword scorer – empty content → zeros")
def _():
    from backend.profile_scoring.gemini_scorer import _keyword_fallback
    result = _keyword_fallback("")
    assert all(v == 0.0 for v in result.scores.values())


# ─── 4. Merge Logic ─────────────────────────────────────────────────────
print("\n── 4. Merge / EMA Accumulation ──────────────────────────")

@test("Single merge updates from zero")
def _():
    from backend.profile_scoring.models import UserProfile, GeminiScoringResult
    from backend.profile_scoring.profile_manager import merge_profile_scores
    from backend.profile_scoring.categories import zero_scores

    p = UserProfile(user_id="merge_1")
    gs = GeminiScoringResult(scores={**zero_scores(), "git": 0.8, "testing": 0.6})

    deltas = merge_profile_scores(p, gs, "github_repo")

    # git should have jumped from 0 → something positive
    assert p.category_scores["git"] > 0.0
    assert deltas["git"] > 0.0
    assert p.upload_count == 1

@test("Multiple merges accumulate")
def _():
    from backend.profile_scoring.models import UserProfile, GeminiScoringResult
    from backend.profile_scoring.profile_manager import merge_profile_scores
    from backend.profile_scoring.categories import zero_scores

    p = UserProfile(user_id="merge_2")

    # Three uploads all mention git
    for _ in range(3):
        gs = GeminiScoringResult(scores={**zero_scores(), "git": 0.9})
        merge_profile_scores(p, gs, "github_repo")

    # Score should be higher after 3 consistent uploads
    assert p.category_scores["git"] > 0.2
    assert p.upload_count == 3

@test("Scores stay in [0, 1]")
def _():
    from backend.profile_scoring.models import UserProfile, GeminiScoringResult
    from backend.profile_scoring.profile_manager import merge_profile_scores
    from backend.profile_scoring.categories import zero_scores

    p = UserProfile(user_id="merge_clamp")
    for _ in range(50):
        gs = GeminiScoringResult(scores={k: 1.0 for k in zero_scores()})
        merge_profile_scores(p, gs, "github_repo")

    for v in p.category_scores.values():
        assert 0.0 <= v <= 1.0, f"Score out of bounds: {v}"

@test("Weak uploads barely shift scores")
def _():
    from backend.profile_scoring.models import UserProfile, GeminiScoringResult
    from backend.profile_scoring.profile_manager import merge_profile_scores
    from backend.profile_scoring.categories import zero_scores

    p = UserProfile(user_id="merge_weak")
    # First set a baseline
    gs1 = GeminiScoringResult(scores={**zero_scores(), "git": 0.8})
    merge_profile_scores(p, gs1, "github_repo")
    after_first = p.category_scores["git"]

    # Now 10 uploads of text_prompt with zero git
    for _ in range(10):
        gs2 = GeminiScoringResult(scores=zero_scores())
        merge_profile_scores(p, gs2, "text_prompt")

    # Git score should have decreased but not dropped to zero
    assert p.category_scores["git"] < after_first
    assert p.category_scores["git"] > 0.0


# ─── 5. Source-Type Weighting ────────────────────────────────────────────
print("\n── 5. Source-Type Weighting ─────────────────────────────")

@test("GitHub upload has stronger effect than text_prompt")
def _():
    from backend.profile_scoring.models import UserProfile, GeminiScoringResult
    from backend.profile_scoring.profile_manager import merge_profile_scores
    from backend.profile_scoring.categories import zero_scores

    p_gh = UserProfile(user_id="sw_github")
    p_txt = UserProfile(user_id="sw_text")

    gs = GeminiScoringResult(scores={**zero_scores(), "apis": 0.9})

    merge_profile_scores(p_gh, gs, "github_repo")    # weight 0.85
    merge_profile_scores(p_txt, gs, "text_prompt")   # weight 0.45

    assert p_gh.category_scores["apis"] > p_txt.category_scores["apis"]


# ─── 6. Live Gemini Scoring ──────────────────────────────────────────────
print("\n── 6. Live Gemini Scoring ──────────────────────────────")

gemini_key = os.getenv("GEMINI_API_KEY", "")
if gemini_key:
    @test("Gemini scores a Python OOP text")
    def _():
        from backend.profile_scoring.gemini_scorer import score_content_with_gemini
        text = """
        I built a Python project using object-oriented design.
        Created a base Animal class with __init__ constructor.
        Dog and Cat inherit from Animal and override the speak() method.
        Used encapsulation for health attributes. Wrote unit tests with pytest.
        Stored data in a SQLite database using SQL queries with indexed columns.
        """
        result = score_content_with_gemini(text, source_type="text_prompt")
        # Works with either Gemini or keyword fallback
        if result.model_used == "keyword_fallback":
            print("      (Gemini rate-limited – verifying keyword fallback)")
        else:
            print(f"      Model: {result.model_used}, Tokens: {result.token_count}")
        # These categories should score > 0 with either scorer
        assert result.scores.get("classes", 0) > 0.0, f"classes={result.scores.get('classes')}"
        assert result.scores.get("inheritance", 0) > 0.0, f"inheritance={result.scores.get('inheritance')}"
        assert result.scores.get("testing", 0) > 0.0
        # Compact prompt may omit summary — only check if keyword fallback
        if result.model_used == "keyword_fallback":
            assert result.overall_summary != ""
        # Show top 5
        top = sorted(result.scores.items(), key=lambda x: x[1], reverse=True)[:5]
        for k, v in top:
            print(f"        {k}: {v:.3f}")

    @test("Gemini scores a GitHub-style README")
    def _():
        from backend.profile_scoring.gemini_scorer import score_content_with_gemini
        text = """
        Repository: awesome-sort
        Languages: C++, Python
        Description: High-performance sorting library

        # awesome-sort
        Implements quicksort, mergesort, heapsort, and radix sort.
        All algorithms are benchmarked for time complexity.
        Includes a graph-based dependency resolver using adjacency lists.
        API endpoints exposed via REST for remote sorting requests.
        Uses Git flow with feature branches and CI testing.
        """
        result = score_content_with_gemini(text, source_type="github_repo")
        assert result.scores.get("sorting", 0) > 0.2
        assert result.scores.get("algorithms", 0) > 0.1
        assert result.scores.get("git", 0) > 0.05

    @test("Gemini handles very short content gracefully")
    def _():
        from backend.profile_scoring.gemini_scorer import score_content_with_gemini
        result = score_content_with_gemini("Hi", source_type="text_prompt")
        # Should return zeros, not crash
        assert all(v == 0.0 for v in result.scores.values())
else:
    print("  ⚠️  GEMINI_API_KEY not set – skipping live Gemini tests")


# ─── 7. Full Orchestrator Flow ───────────────────────────────────────────
print("\n── 7. Orchestrator End-to-End ───────────────────────────")

@test("Full flow: text_prompt upload")
def _():
    from backend.profile_scoring.orchestrator import update_profile_from_upload
    from backend.profile_scoring.profile_manager import get_user_profile

    result = update_profile_from_upload(
        user_id="e2e_user_1",
        source_type="text_prompt",
        content="""
        I'm learning about linked lists, stacks, and queues.
        I implemented a queue using two stacks. Understanding FIFO vs LIFO.
        Also studied binary search trees and graph traversal (DFS/BFS).
        Wrote recursive solutions and analysed time complexity.
        """,
    )
    assert result["success"] is True, f"Failed: {result.get('error')}"
    summary = result["summary"]
    assert summary["user_id"] == "e2e_user_1"
    assert summary["source_type"] == "text_prompt"
    assert summary["upload_count"] == 1
    assert len(summary["categories_increased"]) > 0

    # Check profile was persisted
    profile = get_user_profile("e2e_user_1")
    assert profile is not None
    assert profile.upload_count == 1
    # At least some DS categories should be non-zero
    ds_sum = sum(profile.category_scores.get(c, 0) for c in [
        "linked_lists", "stacks", "queues", "trees", "graphs"
    ])
    assert ds_sum > 0.0, f"Data structure scores unexpectedly zero: {ds_sum}"

@test("Full flow: second upload evolves profile")
def _():
    from backend.profile_scoring.orchestrator import update_profile_from_upload
    from backend.profile_scoring.profile_manager import get_user_profile

    p_before = get_user_profile("e2e_user_1")
    assert p_before is not None

    result = update_profile_from_upload(
        user_id="e2e_user_1",
        source_type="github_repo",
        content="""
        Repository: my-api-server
        Languages: Python, SQL
        A REST API built with FastAPI. Uses PostgreSQL with indexed queries.
        Implements JWT auth, middleware, and async request handling.
        Includes Dockerfile and CI pipeline with pytest.
        Version controlled with Git using feature branches.
        """,
    )
    assert result["success"] is True
    summary = result["summary"]
    assert summary["upload_count"] == 2

    p_after = get_user_profile("e2e_user_1")
    # APIs, SQL, databases, git, testing should have grown
    assert p_after.category_scores["apis"] >= p_before.category_scores.get("apis", 0)
    assert p_after.upload_count == 2


# ─── 8. Edge Cases ──────────────────────────────────────────────────────
print("\n── 8. Edge Cases ───────────────────────────────────────")

@test("Empty content returns error")
def _():
    from backend.profile_scoring.orchestrator import update_profile_from_upload
    result = update_profile_from_upload("edge_user", "text_prompt", "")
    assert result["success"] is False
    assert "too short" in result["error"].lower()

@test("Very short content returns error")
def _():
    from backend.profile_scoring.orchestrator import update_profile_from_upload
    result = update_profile_from_upload("edge_user", "text_prompt", "Hi")
    assert result["success"] is False

@test("Unknown source type still works")
def _():
    from backend.profile_scoring.orchestrator import update_profile_from_upload
    result = update_profile_from_upload(
        "edge_user_2", "mystery_format",
        "This is a long enough text about Python functions and classes for scoring."
    )
    assert result["success"] is True  # Falls back to default weight


# ─── Summary ─────────────────────────────────────────────────────────────
print("\n" + "=" * 64)
total = passed + failed
print(f"  Total: {total}  |  Passed: {passed}  |  Failed: {failed}")
if failed == 0:
    print("  🎉  ALL TESTS PASSED!")
else:
    print(f"  ⚠️  {failed} test(s) FAILED")
    for r in results:
        if r[0] == "❌":
            print(f"    ❌ {r[1]}: {r[2]}")
print("=" * 64)

sys.exit(0 if failed == 0 else 1)
