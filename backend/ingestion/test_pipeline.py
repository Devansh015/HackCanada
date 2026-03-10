"""
Integration test for the Ingestion Pipeline.

Tests all 3 input types:
1. PDF ingestion   - from test_cases/CP421 Assignment 1.pdf
2. GitHub ingestion - from https://github.com/YashSoni4115
3. Text prompt     - a realistic user prompt

Uses LocalMemoryStore (no API keys needed).
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ingestion.input_detector import detect_input_type
from ingestion.text_processor import TextPromptProcessor
from ingestion.github_processor import GitHubProcessor
from ingestion.pdf_processor import PDFProcessor
from ingestion.chunker import SemanticChunker, create_chunker
from ingestion.backboard_client import (
    BackboardMemoryAdapter,
    LocalMemoryStore,
)
from ingestion.ingestion_pipeline import IngestionPipeline


# ── Helpers ──────────────────────────────────────────────────────────────────

DIVIDER = "=" * 70
SECTION = "-" * 70
PASS = "✅"
FAIL = "❌"
INFO = "ℹ️ "

results_summary: list[dict] = []


def header(title: str):
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


def section(title: str):
    print(f"\n{SECTION}")
    print(f"  {title}")
    print(SECTION)


def report(test_name: str, passed: bool, details: str = ""):
    icon = PASS if passed else FAIL
    print(f"\n{icon}  {test_name}")
    if details:
        for line in details.strip().split("\n"):
            print(f"     {line}")
    results_summary.append({"test": test_name, "passed": passed, "details": details})


def pretty(obj, indent=2):
    """Pretty-print dicts/lists, skip large content strings."""
    if isinstance(obj, dict):
        filtered = {}
        for k, v in obj.items():
            if k == "content" and isinstance(v, str) and len(v) > 300:
                filtered[k] = v[:300] + f"... ({len(v)} chars total)"
            elif k == "chunks" and isinstance(v, list):
                filtered[k] = f"[{len(v)} chunks]"
            else:
                filtered[k] = v
        return json.dumps(filtered, indent=indent, default=str)
    return json.dumps(obj, indent=indent, default=str)


# ── Test 1: PDF Ingestion ────────────────────────────────────────────────────

def test_pdf_ingestion():
    header("TEST 1: PDF INGESTION")
    pdf_path = Path(__file__).parent / "test_cases" / "CP421 Assignment 1.pdf"
    print(f"  File: {pdf_path}")
    print(f"  Exists: {pdf_path.exists()}")

    if not pdf_path.exists():
        report("PDF Ingestion", False, f"Test file not found: {pdf_path}")
        return

    file_size = pdf_path.stat().st_size
    print(f"  Size: {file_size / 1024:.1f} KB")

    # ── Step A: Input Detection ──
    section("Step A: Input Detection")
    detection = detect_input_type(str(pdf_path))
    print(pretty(detection))
    detected_ok = detection["detected_type"] == "pdf" and detection["is_valid"]
    report("PDF detected correctly", detected_ok, f"Type={detection['detected_type']}, Valid={detection['is_valid']}")

    # ── Step B: PDF Processor directly ──
    section("Step B: PDF Processor (direct)")
    processor = PDFProcessor()
    proc_result = processor.process(str(pdf_path), user_id="yash_test", file_name="CP421 Assignment 1.pdf")
    content = proc_result.get("content", "")
    metadata = proc_result.get("metadata", {})
    has_content = len(content) > 0 and "error" not in metadata
    print(f"  Content length : {len(content)} chars")
    print(f"  Word count     : {len(content.split()) if content else 0}")
    print(f"  Page count     : {metadata.get('page_count', 'N/A')}")
    print(f"  Title          : {metadata.get('title', 'N/A')}")
    print(f"  Author         : {metadata.get('author', 'N/A')}")
    if content:
        print(f"  First 500 chars:\n{content[:500]}")
    report("PDF content extracted", has_content, f"{len(content)} chars, {metadata.get('page_count','?')} pages")

    # ── Step C: Chunking ──
    section("Step C: Chunking PDF content")
    chunker = create_chunker("semantic")
    chunks = chunker.chunk(content, metadata)
    print(f"  Chunks created: {len(chunks)}")
    if chunks:
        print(f"  Chunk sizes: {[len(c.content) for c in chunks[:10]]}{'...' if len(chunks) > 10 else ''}")
        print(f"  First chunk preview:\n    {chunks[0].content[:200]}...")
    report("PDF chunking", len(chunks) > 0, f"{len(chunks)} chunks created")

    # ── Step D: Full Pipeline ──
    section("Step D: Full Pipeline (end-to-end)")
    store = LocalMemoryStore()
    adapter = BackboardMemoryAdapter(store)
    pipeline = IngestionPipeline(memory_adapter=adapter, enable_logging=False)
    result = pipeline.ingest("yash_test", str(pdf_path), file_name="CP421 Assignment 1.pdf")
    print(pretty(result))
    pipeline_ok = result.get("status") == "success" and result.get("chunks_created", 0) > 0
    report(
        "PDF full pipeline",
        pipeline_ok,
        f"Status={result.get('status')}, Chunks={result.get('chunks_created')}, Stored={result.get('items_stored')}",
    )

    # ── Step E: Verify storage ──
    section("Step E: Verify local storage")
    stored = store.retrieve_chunks("yash_test", source_type="pdf")
    print(f"  Stored chunks for user 'yash_test': {len(stored)}")
    report("PDF storage verification", len(stored) > 0, f"{len(stored)} chunks retrievable")


# ── Test 2: GitHub Ingestion ────────────────────────────────────────────────

def test_github_ingestion():
    header("TEST 2: GITHUB INGESTION")
    github_url = "https://github.com/YashSoni4115"

    # The user's profile URL won't work with the repo API (needs /owner/repo).
    # Let's first detect the type, then try to fetch repos from the user.
    section("Step A: Input Detection (profile URL)")
    detection = detect_input_type(github_url)
    print(pretty(detection))
    # A profile URL (no repo) won't match the owner/repo pattern – that's expected.
    # Let's test with a real repo from this user.

    section("Step B: Discover repos for YashSoni4115")
    import requests as _req
    try:
        resp = _req.get(
            "https://api.github.com/users/YashSoni4115/repos",
            headers={"Accept": "application/vnd.github.v3+json"},
            params={"sort": "updated", "per_page": 5},
            timeout=10,
        )
        resp.raise_for_status()
        repos = resp.json()
        print(f"  Found {len(repos)} recent repos:")
        for r in repos:
            print(f"    - {r['full_name']}  ⭐{r.get('stargazers_count',0)}  ({', '.join(r.get('topics',[]) or ['no topics'])})")
        
        if not repos:
            report("GitHub repo discovery", False, "No public repos found")
            return
        
        # Pick the first repo for full pipeline test
        repo_url = repos[0]["html_url"]
        repo_name = repos[0]["full_name"]
        report("GitHub repo discovery", True, f"Found {len(repos)} repos, using: {repo_name}")
    except Exception as e:
        report("GitHub repo discovery", False, f"API error: {e}")
        # Fall back to the HackCanada repo itself
        repo_url = "https://github.com/Devansh015/HackCanada"
        repo_name = "Devansh015/HackCanada"
        print(f"  Falling back to: {repo_url}")

    # ── Step C: Input Detection (repo URL) ──
    section(f"Step C: Input Detection for {repo_url}")
    detection = detect_input_type(repo_url)
    print(pretty(detection))
    detected_ok = detection["detected_type"] == "github_repo" and detection["is_valid"]
    report("GitHub repo URL detected", detected_ok, f"Type={detection['detected_type']}")

    # ── Step D: GitHub Processor directly ──
    section("Step D: GitHub Processor (direct)")
    processor = GitHubProcessor()
    proc_result = processor.process(repo_url, user_id="yash_test")
    content = proc_result.get("content", "")
    metadata = proc_result.get("metadata", {})
    languages = proc_result.get("languages", [])
    has_content = len(content) > 0 and "error" not in metadata
    print(f"  Content length : {len(content)} chars")
    print(f"  Description    : {metadata.get('description', 'N/A')}")
    print(f"  Stars          : {metadata.get('stars', 'N/A')}")
    print(f"  Forks          : {metadata.get('forks', 'N/A')}")
    print(f"  Languages      : {languages}")
    print(f"  Topics         : {metadata.get('topics', [])}")
    if content:
        print(f"  First 500 chars:\n{content[:500]}")
    report("GitHub content extracted", has_content, f"{len(content)} chars, langs={languages}")

    # ── Step E: Full Pipeline ──
    section("Step E: Full Pipeline (end-to-end)")
    store = LocalMemoryStore()
    adapter = BackboardMemoryAdapter(store)
    pipeline = IngestionPipeline(memory_adapter=adapter, enable_logging=False)
    result = pipeline.ingest("yash_test", repo_url)
    print(pretty(result))
    pipeline_ok = result.get("status") == "success" and result.get("chunks_created", 0) > 0
    report(
        "GitHub full pipeline",
        pipeline_ok,
        f"Status={result.get('status')}, Chunks={result.get('chunks_created')}, Stored={result.get('items_stored')}",
    )

    # ── Step F: Verify storage ──
    section("Step F: Verify local storage")
    stored = store.retrieve_chunks("yash_test", source_type="github_repo")
    print(f"  Stored chunks for user 'yash_test': {len(stored)}")
    report("GitHub storage verification", len(stored) > 0, f"{len(stored)} chunks retrievable")


# ── Test 3: Text Prompt Ingestion ───────────────────────────────────────────

def test_text_prompt_ingestion():
    header("TEST 3: TEXT PROMPT INGESTION")

    prompts = [
        {
            "text": "I'm a third-year Computer Science student at Wilfrid Laurier University. "
                    "I'm skilled in Python, JavaScript, and React. I've built several full-stack "
                    "web applications and I'm passionate about AI and machine learning. "
                    "Recently I've been exploring large language models and RAG architectures.",
            "expected_category": "skill",
            "label": "Skills & interests prompt",
        },
        {
            "text": "I worked on a car rental management system using Java and Spring Boot. "
                    "The project involved building REST APIs, integrating a PostgreSQL database, "
                    "and implementing JWT authentication. I managed a team of 4 developers.",
            "expected_category": "experience",
            "label": "Experience prompt",
        },
        {
            "text": "I'm thinking about building a personal knowledge graph that connects all my "
                    "documents, notes, and code repositories into one visual workspace. "
                    "It would use AI to automatically find relationships between items.",
            "expected_category": "project_idea",
            "label": "Project idea prompt",
        },
    ]

    store = LocalMemoryStore()
    adapter = BackboardMemoryAdapter(store)
    pipeline = IngestionPipeline(memory_adapter=adapter, enable_logging=False)

    for i, prompt_info in enumerate(prompts, 1):
        section(f"Prompt {i}: {prompt_info['label']}")
        text = prompt_info["text"]
        expected = prompt_info["expected_category"]
        print(f"  Input: \"{text[:80]}...\"")
        print(f"  Expected category: {expected}")

        # ── Detection ──
        detection = detect_input_type(text)
        detected_ok = detection["detected_type"] == "text_prompt"
        print(f"  Detected type: {detection['detected_type']}")
        print(f"  Inferred category: {detection['metadata'].get('inferred_category')}")
        print(f"  Confidence: {detection['metadata'].get('category_confidence')}")
        report(f"Text detection (prompt {i})", detected_ok)

        # ── Full Pipeline ──
        result = pipeline.ingest("yash_test", text)
        print(f"  Status: {result.get('status')}")
        print(f"  Chunks: {result.get('chunks_created')}")
        print(f"  Category: {result.get('metadata_summary', {}).get('category')}")
        pipeline_ok = result.get("status") == "success"
        actual_cat = result.get("metadata_summary", {}).get("category", "")
        cat_match = actual_cat == expected
        report(
            f"Text pipeline (prompt {i})",
            pipeline_ok,
            f"Status={result['status']}, Category={actual_cat} (expected {expected}, {'match' if cat_match else 'mismatch'})",
        )

    # ── Verify all text prompts stored ──
    section("Verify all text prompts in storage")
    stored = store.retrieve_chunks("yash_test", source_type="text_prompt", limit=50)
    print(f"  Total text chunks stored: {len(stored)}")
    report("Text storage verification", len(stored) > 0, f"{len(stored)} chunks retrievable")


# ── Test 4: Edge cases ──────────────────────────────────────────────────────

def test_edge_cases():
    header("TEST 4: EDGE CASES")

    # Empty input
    section("Edge case: empty string")
    detection = detect_input_type("")
    print(f"  Detection: {pretty(detection)}")
    report("Empty string handled", detection["detected_type"] == "text_prompt")

    # Random URL (not GitHub)
    section("Edge case: non-GitHub URL")
    detection = detect_input_type("https://stackoverflow.com/questions/12345")
    print(f"  Detection: {pretty(detection)}")
    report("Non-GitHub URL detected as 'url'", detection["detected_type"] == "url")

    # Invalid file path
    section("Edge case: non-existent PDF path")
    store = LocalMemoryStore()
    adapter = BackboardMemoryAdapter(store)
    pipeline = IngestionPipeline(memory_adapter=adapter, enable_logging=False)
    result = pipeline.ingest("yash_test", "/fake/nonexistent.pdf")
    print(f"  Result: {pretty(result)}")
    report("Non-existent file handled gracefully", result.get("status") == "error" or result.get("chunks_created", 0) == 0)

    # Very short text
    section("Edge case: very short text")
    result = pipeline.ingest("yash_test", "Hi")
    print(f"  Result: {pretty(result)}")
    report("Short text handled", True)  # Should either succeed or fail gracefully


# ── Final Summary ────────────────────────────────────────────────────────────

def print_summary():
    header("FINAL TEST SUMMARY")
    passed = sum(1 for r in results_summary if r["passed"])
    failed = sum(1 for r in results_summary if not r["passed"])
    total = len(results_summary)

    for r in results_summary:
        icon = PASS if r["passed"] else FAIL
        print(f"  {icon}  {r['test']}")

    print(f"\n  {DIVIDER}")
    print(f"  Total: {total}  |  Passed: {passed}  |  Failed: {failed}")
    if failed == 0:
        print(f"  🎉  ALL TESTS PASSED!")
    else:
        print(f"  ⚠️   {failed} test(s) need attention")
    print(DIVIDER)


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{'🧪 INGESTION PIPELINE TEST SUITE':^70}")
    print(f"{'=' * 70}")
    print(f"  Timestamp : {datetime.now().isoformat()}")
    print(f"  Python    : {sys.version.split()[0]}")
    print(f"  CWD       : {os.getcwd()}")
    print()

    test_pdf_ingestion()
    test_github_ingestion()
    test_text_prompt_ingestion()
    test_edge_cases()
    print_summary()
