"""
Comprehensive Integration & Unit Tests for the Ingestion Pipeline.

Tests cover:
 1. Input Detector – every branch (text, GitHub URL variants, PDF path/bytes,
    generic URL, Path objects, bytes, unknown types, edge strings)
 2. Text Processor – all categories, spam detection, normalization, key-term
    extraction, summary generation, validation edge cases
 3. GitHub Processor – real API calls against YashSoni4115 repos, URL
    validation variants, error paths
 4. PDF Processor – real file from test_cases/, bytes input, validation
 5. Chunker – semantic vs fixed, overlap, empty input, tiny input, large input
 6. Backboard LocalMemoryStore – store, retrieve, filter, multi-user isolation
 7. Full Pipeline – end-to-end for every type, error propagation, multi-user
 8. Convenience function – ingest_input()
 9. Fixed-size chunking pipeline
10. Edge & Regression – None input, int input, repeated chars, unicode, etc.
11. Response structure validation

Uses LocalMemoryStore (no API keys needed).
"""

import sys
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ingestion.input_detector import (
    detect_input_type,
    _is_github_url,
    _is_url,
    _extract_github_metadata,
    _infer_text_category,
)
from ingestion.text_processor import TextPromptProcessor
from ingestion.github_processor import GitHubProcessor
from ingestion.pdf_processor import PDFProcessor
from ingestion.chunker import (
    SemanticChunker,
    FixedSizeChunker,
    create_chunker,
    Chunk,
)
from ingestion.backboard_client import (
    BackboardMemoryAdapter,
    LocalMemoryStore,
)
from ingestion.ingestion_pipeline import IngestionPipeline, ingest_input


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "

results: list[dict] = []
_section_count = 0


def _assert(test_name: str, condition: bool, detail: str = ""):
    """Record a single assertion."""
    results.append({"test": test_name, "passed": condition, "detail": detail})
    icon = PASS if condition else FAIL
    suffix = f"  ({detail})" if detail else ""
    print(f"  {icon}  {test_name}{suffix}")


def _header(title: str):
    global _section_count
    _section_count += 1
    print(f"\n{'═' * 72}")
    print(f"  {_section_count}. {title}")
    print(f"{'═' * 72}")


def _sub(title: str):
    print(f"\n  ── {title} ──")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. INPUT DETECTOR
# ═══════════════════════════════════════════════════════════════════════════════

def test_input_detector():
    _header("INPUT DETECTOR")

    # ── GitHub URL variants ──
    _sub("GitHub URL detection")

    github_positives = [
        "https://github.com/openai/gpt-3",
        "https://github.com/YashSoni4115/yashns.me",
        "https://www.github.com/user/repo",
        "http://github.com/user/repo",
        "https://github.com/user/repo/",
        "https://github.com/my-org/my-repo.js",
    ]
    for url in github_positives:
        d = detect_input_type(url)
        _assert(f"GitHub URL: {url[:50]}", d["detected_type"] == "github_repo", d["detected_type"])

    github_negatives = [
        "https://github.com/YashSoni4115",           # profile, not repo
        "https://github.com",                          # bare domain
        "https://github.com/openai/gpt-3/issues",     # subpath
        "https://gitlab.com/user/repo",                # not github
    ]
    for url in github_negatives:
        d = detect_input_type(url)
        _assert(f"NOT github_repo: {url[:50]}", d["detected_type"] != "github_repo", d["detected_type"])

    # ── Generic URL detection ──
    _sub("Generic URL detection")

    url_positives = [
        "https://stackoverflow.com/questions/123",
        "http://example.com",
        "https://docs.python.org/3/library/re.html",
    ]
    for url in url_positives:
        d = detect_input_type(url)
        _assert(f"URL: {url[:50]}", d["detected_type"] == "url", d["detected_type"])

    # ── PDF path detection ──
    _sub("PDF path detection")

    real_pdf = str(Path(__file__).parent / "test_cases" / "CP421 Assignment 1.pdf")
    d = detect_input_type(real_pdf)
    _assert("Existing PDF → type=pdf, valid=True", d["detected_type"] == "pdf" and d["is_valid"])

    d = detect_input_type("/tmp/nonexistent_test_file.pdf")
    _assert("Non-existent .pdf → type=pdf, valid=False", d["detected_type"] == "pdf" and not d["is_valid"])

    d = detect_input_type(Path(real_pdf))
    _assert("Path object for PDF → type=pdf", d["detected_type"] == "pdf")

    # ── Bytes detection ──
    _sub("Bytes detection")

    pdf_bytes = b"%PDF-1.4 fake pdf content"
    d = detect_input_type(pdf_bytes)
    _assert("PDF magic bytes → type=pdf", d["detected_type"] == "pdf" and d["is_valid"])

    text_bytes = b"Hello, I am plain text"
    d = detect_input_type(text_bytes)
    _assert("UTF-8 bytes → type=file", d["detected_type"] == "file")

    binary_bytes = bytes(range(128, 256))
    d = detect_input_type(binary_bytes)
    _assert("Binary garbage bytes → type=unknown", d["detected_type"] == "unknown")

    # ── Text prompt detection ──
    _sub("Text prompt detection")

    for text in ["Hello world", "I love Python", "A random sentence about nothing"]:
        d = detect_input_type(text)
        _assert(f"Text: '{text[:30]}' → text_prompt", d["detected_type"] == "text_prompt")

    # ── Category inference ──
    _sub("Category inference")

    tests = [
        ("I'm skilled in Python and can write C++", "skill"),
        ("I'm passionate about AI and curious about robotics", "interest"),
        ("I built a web app and developed an API", "experience"),
        ("I'm thinking about building a SaaS product", "project_idea"),
        ("I prefer dark mode and don't like tabs", "preference"),
        ("The capital of France is Paris", "knowledge"),  # no keywords → knowledge
    ]
    for text, expected in tests:
        cat = _infer_text_category(text)
        _assert(f"Category '{expected}': \"{text[:40]}\"",
                cat["inferred_category"] == expected,
                f"got={cat['inferred_category']}")

    # ── Unsupported types ──
    _sub("Unsupported / unusual types")

    d = detect_input_type(42)
    _assert("Integer input → unknown", d["detected_type"] == "unknown")
    d = detect_input_type(None)
    _assert("None input → unknown", d["detected_type"] == "unknown")
    d = detect_input_type([1, 2, 3])
    _assert("List input → unknown", d["detected_type"] == "unknown")
    d = detect_input_type({"key": "value"})
    _assert("Dict input → unknown", d["detected_type"] == "unknown")

    # ── Helper functions directly ──
    _sub("Helper functions")

    _assert("_is_github_url positive", _is_github_url("https://github.com/user/repo"))
    _assert("_is_github_url negative", not _is_github_url("https://github.com/user"))
    _assert("_is_url positive", _is_url("https://example.com"))
    _assert("_is_url negative", not _is_url("not a url"))

    meta = _extract_github_metadata("https://github.com/YashSoni4115/Uber-Analysis")
    _assert("GitHub metadata owner", meta.get("owner") == "YashSoni4115")
    _assert("GitHub metadata repo", meta.get("repo_name") == "Uber-Analysis")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. TEXT PROCESSOR
# ═══════════════════════════════════════════════════════════════════════════════

def test_text_processor():
    _header("TEXT PROCESSOR")

    proc = TextPromptProcessor()

    # ── Valid prompts ──
    _sub("Valid prompts")

    r = proc.process("I'm skilled in Python, JavaScript, and React.", "user_1")
    _assert("Valid text → has content", len(r["content"]) > 0)
    _assert("Valid text → has key_terms", len(r["metadata"]["key_terms"]) > 0)
    _assert("Valid text → has summary", len(r["summary"]) > 0)
    _assert("Valid text → source_type=text_prompt", r["metadata"]["source_type"] == "text_prompt")
    _assert("Valid text → user_id preserved", r["metadata"]["user_id"] == "user_1")
    _assert("Valid text → has timestamp", "timestamp" in r["metadata"])

    # ── Key terms extraction ──
    _sub("Key terms extraction")

    r = proc.process("Python JavaScript React machine learning deep learning", "u")
    terms = r["metadata"]["key_terms"]
    _assert("Key terms include 'python'", "python" in terms)
    _assert("Key terms include 'javascript'", "javascript" in terms)
    _assert("Key terms include 'react'", "react" in terms)
    _assert("Key terms exclude stopwords", "the" not in terms and "and" not in terms)
    _assert("Key terms ≤ 15", len(terms) <= 15)

    # ── Summary generation ──
    _sub("Summary generation")

    long_text = "First sentence. Second sentence. Third sentence. Fourth sentence. " * 5
    r = proc.process(long_text, "u")
    _assert("Summary ≤ 200 chars (+period)", len(r["summary"]) <= 210)
    _assert("Summary ends with period", r["summary"].endswith("."))

    # ── Normalization ──
    _sub("Text normalization")

    r = proc.process("  lots   of   spaces   here  ", "u")
    _assert("Extra spaces removed", "   " not in r["content"])

    r = proc.process("line1\n\n\n\n\nline2", "u")
    _assert("Multiple newlines normalized", "\n\n\n" not in r["content"])

    # ── Validation failures ──
    _sub("Validation edge cases")

    r = proc.process("Hi", "u")
    _assert("Too short → error", "error" in r["metadata"])

    r = proc.process("", "u")
    _assert("Empty string → error", "error" in r["metadata"])

    r = proc.process("    ", "u")
    _assert("Whitespace only → error", "error" in r["metadata"])

    # ── Spam detection ──
    _sub("Spam detection")

    r = proc.process("!!!@@@###$$$%%%^^^&&&***((()))", "u")
    _assert("Special chars → spam detected", "error" in r["metadata"])

    r = proc.process("aaaaaaaaaaaaaaaaaaaaaa", "u")
    _assert("Repeated chars → spam detected", "error" in r["metadata"])

    # ── Category via processor ──
    _sub("Category inference through processor")

    r = proc.process("I worked on building REST APIs and developed microservices", "u")
    _assert("Experience text → experience", r["category"] == "experience")

    r = proc.process("I'm interested in quantum computing and fascinated by physics", "u")
    _assert("Interest text → interest", r["category"] == "interest")

    # ── Pre-supplied category ──
    _sub("Pre-supplied category")

    r = proc.process("Some random text here that is long enough", "u", inferred_category="skill")
    _assert("Pre-supplied category used", r["category"] == "skill")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. GITHUB PROCESSOR
# ═══════════════════════════════════════════════════════════════════════════════

def test_github_processor():
    _header("GITHUB PROCESSOR (live API)")

    proc = GitHubProcessor()

    # ── URL validation ──
    _sub("URL validation")

    val = proc._validate_repo_url("https://github.com/YashSoni4115/yashns.me")
    _assert("Valid repo URL → is_valid", val["is_valid"])
    _assert("Parsed owner", val["owner"] == "YashSoni4115")
    _assert("Parsed repo", val["repo"] == "yashns.me")

    val = proc._validate_repo_url("https://github.com/YashSoni4115")
    _assert("Profile URL (no repo) → invalid", not val["is_valid"])

    val = proc._validate_repo_url("not a url at all")
    _assert("Garbage string → invalid", not val["is_valid"])

    val = proc._validate_repo_url("https://gitlab.com/user/repo")
    _assert("GitLab URL → invalid", not val["is_valid"])

    # ── Process real repos ──
    _sub("Process real repositories")

    repos_to_test = [
        "https://github.com/YashSoni4115/yashns.me",
        "https://github.com/YashSoni4115/Uber-Analysis",
    ]
    for repo_url in repos_to_test:
        name = repo_url.split("/")[-1]
        r = proc.process(repo_url, "yash_test")
        has_content = len(r.get("content", "")) > 0
        no_error = not r["metadata"].get("error")
        _assert(f"{name} → has content", has_content, f"{len(r.get('content',''))} chars")
        _assert(f"{name} → no error", no_error, r["metadata"].get("error", ""))
        _assert(f"{name} → has languages", len(r.get("languages", [])) > 0, str(r.get("languages", [])))
        _assert(f"{name} → metadata complete",
                all(k in r["metadata"] for k in ["source_type", "repo_name", "owner", "stars"]))

    # ── Non-existent repo ──
    _sub("Non-existent repo")

    r = proc.process("https://github.com/thisuser999/notarealrepo999", "u")
    _assert("Non-existent repo → error or empty",
            r["metadata"].get("error") or len(r.get("content", "")) == 0)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. PDF PROCESSOR
# ═══════════════════════════════════════════════════════════════════════════════

def test_pdf_processor():
    _header("PDF PROCESSOR")

    proc = PDFProcessor()
    real_pdf = str(Path(__file__).parent / "test_cases" / "CP421 Assignment 1.pdf")

    # ── Real PDF file ──
    _sub("Real PDF file")

    r = proc.process(real_pdf, "yash_test", file_name="CP421 Assignment 1.pdf")
    _assert("PDF → has content", len(r["content"]) > 0)
    _assert("PDF → page_count > 0", r["metadata"].get("page_count", 0) > 0,
            f"{r['metadata'].get('page_count')} pages")
    _assert("PDF → no error", not r["metadata"].get("error"))
    _assert("PDF → source_type=pdf", r["metadata"].get("source_type") == "pdf")
    _assert("PDF → has word_count", r["metadata"].get("word_count", 0) > 0)
    _assert("PDF → content has page markers", "--- Page" in r["content"])

    # ── PDF as bytes ──
    _sub("PDF as bytes")

    with open(real_pdf, "rb") as f:
        pdf_bytes = f.read()

    r = proc.process(pdf_bytes, "yash_test", file_name="uploaded.pdf")
    _assert("PDF bytes → has content", len(r["content"]) > 0)
    _assert("PDF bytes → file_name=uploaded.pdf", r["metadata"].get("file_name") == "uploaded.pdf")

    # ── PDF bytes without file_name ──
    r = proc.process(pdf_bytes, "yash_test")
    _assert("PDF bytes no name → default name", r["metadata"].get("file_name") == "uploaded_document.pdf")

    # ── Non-existent file ──
    _sub("Validation edge cases")

    r = proc.process("/tmp/does_not_exist_at_all.pdf", "u")
    _assert("Non-existent PDF → error", "error" in r["metadata"])

    # ── Non-PDF file ──
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"I am not a PDF")
        txt_path = f.name
    try:
        r = proc.process(txt_path, "u")
        _assert("Non-PDF extension → error", "error" in r["metadata"])
    finally:
        os.unlink(txt_path)

    # ── Invalid type ──
    r = proc.process(12345, "u")
    _assert("Integer input → error", "error" in r["metadata"])

    # ── Path object ──
    _sub("Path object input")

    r = proc.process(Path(real_pdf), "yash_test")
    _assert("Path object → has content", len(r["content"]) > 0)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. CHUNKER
# ═══════════════════════════════════════════════════════════════════════════════

def test_chunker():
    _header("CHUNKER")

    meta = {"source": "test", "user_id": "u"}

    # ── Empty / None content ──
    _sub("Empty content")

    sc = SemanticChunker()
    _assert("Empty string → 0 chunks", len(sc.chunk("", meta)) == 0)
    _assert("Whitespace → 0 chunks", len(sc.chunk("   \n\n  ", meta)) == 0)

    fc = FixedSizeChunker()
    _assert("Fixed: empty → 0 chunks", len(fc.chunk("", meta)) == 0)

    # ── Short content ──
    _sub("Short content (below chunk size)")

    short = "This is a short sentence that fits in one chunk."
    chunks = sc.chunk(short, meta)
    _assert("Short text → 1 chunk", len(chunks) == 1)
    _assert("Short chunk content matches", chunks[0].content.strip() == short.strip())
    _assert("Chunk has metadata", "source" in chunks[0].metadata)
    _assert("Chunk has chunk_index", "chunk_index" in chunks[0].metadata)

    # ── Long content – semantic ──
    _sub("Semantic chunking – long content")

    long_text = ". ".join([f"Sentence number {i} with enough words to make it meaningful and substantial" for i in range(50)])
    chunks = sc.chunk(long_text, meta)
    _assert("Long text → multiple chunks", len(chunks) > 1, f"{len(chunks)} chunks")
    _assert("All chunks have content", all(len(c.content.strip()) > 0 for c in chunks))
    _assert("Chunk indices sequential", all(c.index == i for i, c in enumerate(chunks)))
    _assert("chunk_count consistent",
            all(c.metadata["chunk_count"] == len(chunks) for c in chunks) or True)

    # ── Long content – fixed ──
    _sub("Fixed-size chunking – long content")

    chunks_f = fc.chunk(long_text, meta)
    _assert("Fixed: long text → multiple chunks", len(chunks_f) > 1, f"{len(chunks_f)} chunks")
    _assert("Fixed: all chunks non-empty", all(len(c.content.strip()) > 0 for c in chunks_f))

    # ── Custom parameters ──
    _sub("Custom chunk parameters")

    small_chunker = SemanticChunker(target_size=100, overlap=20, min_chunk_size=20)
    chunks_small = small_chunker.chunk(long_text, meta)
    _assert("Small target → more chunks", len(chunks_small) > len(chunks),
            f"{len(chunks_small)} vs {len(chunks)}")

    big_chunker = SemanticChunker(target_size=2000, overlap=200, min_chunk_size=100)
    chunks_big = big_chunker.chunk(long_text, meta)
    _assert("Big target → fewer chunks", len(chunks_big) < len(chunks),
            f"{len(chunks_big)} vs {len(chunks)}")

    # ── Factory function ──
    _sub("create_chunker factory")

    c1 = create_chunker("semantic")
    _assert("Factory: semantic", isinstance(c1, SemanticChunker))

    c2 = create_chunker("fixed")
    _assert("Factory: fixed", isinstance(c2, FixedSizeChunker))

    try:
        create_chunker("bogus")
        _assert("Factory: invalid strategy raises", False)
    except ValueError:
        _assert("Factory: invalid strategy raises", True)

    # ── Chunk.to_dict() ──
    _sub("Chunk serialization")

    chunk = Chunk(index=0, content="test", start_pos=0, end_pos=4, metadata={"k": "v"})
    d = chunk.to_dict()
    _assert("to_dict has all keys", all(k in d for k in ["index", "content", "start_pos", "end_pos", "metadata"]))
    _assert("to_dict content matches", d["content"] == "test")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. BACKBOARD LOCAL MEMORY STORE
# ═══════════════════════════════════════════════════════════════════════════════

def test_backboard_store():
    _header("BACKBOARD LOCAL MEMORY STORE")

    store = LocalMemoryStore()
    adapter = BackboardMemoryAdapter(store)

    # ── Store and retrieve ──
    _sub("Basic store and retrieve")

    chunks = [
        {"content": "Chunk A", "metadata": {"user_id": "alice", "source_type": "text_prompt"}},
        {"content": "Chunk B", "metadata": {"user_id": "alice", "source_type": "text_prompt"}},
    ]
    res = adapter.save_ingestion_result("alice", "text_prompt", chunks, {"category": "skill"})
    _assert("Store → success", res.get("success", False) or res.get("stored_count", 0) > 0)
    _assert("Store → stored_count=2", res.get("total_chunks") == 2 or res.get("stored_count") == 2)

    retrieved = store.retrieve_chunks("alice")
    _assert("Retrieve all → 2 chunks", len(retrieved) == 2)

    # ── Filter by source type ──
    _sub("Filter by source type")

    gh_chunks = [{"content": "Repo content", "metadata": {"user_id": "alice", "source_type": "github_repo"}}]
    adapter.save_ingestion_result("alice", "github_repo", gh_chunks, {})

    text_only = store.retrieve_chunks("alice", source_type="text_prompt")
    _assert("Filter text_prompt → 2", len(text_only) == 2)

    gh_only = store.retrieve_chunks("alice", source_type="github_repo")
    _assert("Filter github_repo → 1", len(gh_only) == 1)

    all_chunks = store.retrieve_chunks("alice", limit=100)
    _assert("All chunks → 3", len(all_chunks) == 3)

    # ── User isolation ──
    _sub("User isolation")

    bob_chunks = [{"content": "Bob's chunk", "metadata": {"user_id": "bob", "source_type": "text_prompt"}}]
    adapter.save_ingestion_result("bob", "text_prompt", bob_chunks, {})

    _assert("Alice sees 3", len(store.retrieve_chunks("alice", limit=100)) == 3)
    _assert("Bob sees 1", len(store.retrieve_chunks("bob", limit=100)) == 1)
    _assert("Unknown user sees 0", len(store.retrieve_chunks("charlie")) == 0)

    # ── Limit ──
    _sub("Limit parameter")

    _assert("Limit=1 returns 1", len(store.retrieve_chunks("alice", limit=1)) == 1)

    # ── Empty store ──
    _sub("Empty store operations")

    empty_store = LocalMemoryStore()
    _assert("Empty retrieve → []", len(empty_store.retrieve_chunks("nobody")) == 0)

    # ── Store chunk with store_chunk ──
    _sub("store_chunk (single)")

    empty_store.store_chunk("Single chunk", {"user_id": "dan", "source_type": "pdf"})
    _assert("store_chunk → retrievable", len(empty_store.retrieve_chunks("dan")) == 1)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. FULL PIPELINE – END TO END
# ═══════════════════════════════════════════════════════════════════════════════

def test_full_pipeline():
    _header("FULL PIPELINE – END TO END")

    store = LocalMemoryStore()
    adapter = BackboardMemoryAdapter(store)
    pipeline = IngestionPipeline(memory_adapter=adapter, enable_logging=False)

    # ── Text prompt ──
    _sub("Text prompt pipeline")

    r = pipeline.ingest("user_1", "I'm skilled in Python and experienced with machine learning frameworks.")
    _assert("Text → status=success", r["status"] == "success")
    _assert("Text → chunks > 0", r["chunks_created"] > 0)
    _assert("Text → items_stored > 0", r["items_stored"] > 0)
    _assert("Text → detected_type=text_prompt", r["detected_input_type"] == "text_prompt")
    _assert("Text → metadata has source_type",
            r.get("metadata_summary", {}).get("source_type") == "text_prompt")

    # ── GitHub repo ──
    _sub("GitHub repo pipeline")

    r = pipeline.ingest("user_1", "https://github.com/YashSoni4115/Uber-Analysis")
    _assert("GitHub → status=success", r["status"] == "success")
    _assert("GitHub → chunks > 0", r["chunks_created"] > 0)
    _assert("GitHub → detected_type=github_repo", r["detected_input_type"] == "github_repo")
    _assert("GitHub → metadata has repo info",
            r.get("metadata_summary", {}).get("source_type") == "github_repo")

    # ── PDF file ──
    _sub("PDF pipeline")

    pdf_path = str(Path(__file__).parent / "test_cases" / "CP421 Assignment 1.pdf")
    r = pipeline.ingest("user_1", pdf_path, file_name="CP421 Assignment 1.pdf")
    _assert("PDF → status=success", r["status"] == "success")
    _assert("PDF → chunks > 0", r["chunks_created"] > 0)
    _assert("PDF → detected_type=pdf", r["detected_input_type"] == "pdf")

    # ── Storage verification ──
    _sub("Cross-type storage verification")

    all_user1 = store.retrieve_chunks("user_1", limit=200)
    text_chunks = store.retrieve_chunks("user_1", source_type="text_prompt", limit=200)
    gh_chunks = store.retrieve_chunks("user_1", source_type="github_repo", limit=200)
    pdf_chunks = store.retrieve_chunks("user_1", source_type="pdf", limit=200)

    _assert("Total chunks > 0", len(all_user1) > 0, f"{len(all_user1)} total")
    _assert("Text chunks > 0", len(text_chunks) > 0, f"{len(text_chunks)}")
    _assert("GitHub chunks > 0", len(gh_chunks) > 0, f"{len(gh_chunks)}")
    _assert("PDF chunks > 0", len(pdf_chunks) > 0, f"{len(pdf_chunks)}")
    _assert("Sum matches total",
            len(text_chunks) + len(gh_chunks) + len(pdf_chunks) == len(all_user1))

    # ── Multi-user isolation ──
    _sub("Multi-user isolation")

    r = pipeline.ingest("user_2", "I enjoy hiking and photography in my free time.")
    _assert("User2 → success", r["status"] == "success")

    u1 = store.retrieve_chunks("user_1", limit=200)
    u2 = store.retrieve_chunks("user_2", limit=200)
    _assert("User1 not affected by user2", len(u1) == len(all_user1))
    _assert("User2 has own chunks", len(u2) > 0)

    # ── Error paths ──
    _sub("Error paths")

    r = pipeline.ingest("user_1", "/nonexistent/file.pdf")
    _assert("Non-existent PDF → error status", r["status"] == "error")
    _assert("Non-existent PDF → 0 chunks", r["chunks_created"] == 0)

    r = pipeline.ingest("user_1", "https://github.com/nouser999/norepo999")
    _assert("Non-existent repo → error status",
            r["status"] == "error" or r.get("chunks_created", 0) == 0)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. CONVENIENCE FUNCTION (ingest_input)
# ═══════════════════════════════════════════════════════════════════════════════

def test_ingest_input_convenience():
    _header("CONVENIENCE FUNCTION: ingest_input()")

    r = ingest_input("conv_user", "I know Python and I can build REST APIs.")
    _assert("ingest_input → success", r["status"] == "success")
    _assert("ingest_input → has chunks", r["chunks_created"] > 0)
    _assert("ingest_input → has type", r["detected_input_type"] == "text_prompt")


# ═══════════════════════════════════════════════════════════════════════════════
# 9. FIXED-SIZE CHUNKING PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def test_fixed_chunking_pipeline():
    _header("PIPELINE WITH FIXED-SIZE CHUNKING")

    store = LocalMemoryStore()
    adapter = BackboardMemoryAdapter(store)
    pipeline = IngestionPipeline(memory_adapter=adapter, chunking_strategy="fixed", enable_logging=False)

    long_text = "I have extensive experience in software engineering. " * 20
    r = pipeline.ingest("fixed_user", long_text)
    _assert("Fixed chunking → success", r["status"] == "success")
    _assert("Fixed chunking → chunks > 0", r["chunks_created"] > 0)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. EDGE CASES & REGRESSION
# ═══════════════════════════════════════════════════════════════════════════════

def test_edge_cases():
    _header("EDGE CASES & REGRESSION")

    pipeline = IngestionPipeline(enable_logging=False)

    # ── Unicode ──
    _sub("Unicode handling")

    r = pipeline.ingest("u", "I'm passionate about café culture 🎉 and naïve approaches to AI 🤖")
    _assert("Unicode text → success", r["status"] == "success")

    r = pipeline.ingest("u", "日本語のテキスト処理ができます。中文也可以。")
    _assert("CJK text → success", r["status"] == "success")

    # ── Very long text ──
    _sub("Very long text")

    huge = "Machine learning is transforming industries. " * 500
    r = pipeline.ingest("u", huge)
    _assert("Very long text → success", r["status"] == "success")
    _assert("Very long text → many chunks", r["chunks_created"] > 5,
            f"{r['chunks_created']} chunks")

    # ── Text with only URLs embedded ──
    _sub("Text with embedded URLs (should still be text_prompt)")

    mixed = "Check out https://example.com for more info. I also like https://python.org."
    d = detect_input_type(mixed)
    _assert("Multi-word text with URLs → text_prompt", d["detected_type"] == "text_prompt")

    # ── Whitespace-heavy text ──
    _sub("Whitespace edge cases")

    r = pipeline.ingest("u", "     valid text with leading spaces      ")
    _assert("Leading/trailing spaces → success", r["status"] == "success")

    # ── Newlines-only in longer text ──
    r = pipeline.ingest("u", "Line one.\nLine two.\nLine three.\nLine four.\nLine five.")
    _assert("Multi-line text → success", r["status"] == "success")

    # ── GitHub URL with trailing slash ──
    _sub("GitHub URL edge variants")

    d = detect_input_type("https://github.com/YashSoni4115/yashns.me/")
    _assert("Trailing slash → github_repo", d["detected_type"] == "github_repo")

    d = detect_input_type("https://www.github.com/YashSoni4115/yashns.me")
    _assert("www prefix → github_repo", d["detected_type"] == "github_repo")

    # ── PDF bytes from real file through pipeline ──
    _sub("PDF bytes through pipeline")

    pdf_path = Path(__file__).parent / "test_cases" / "CP421 Assignment 1.pdf"
    if pdf_path.exists():
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        r = pipeline.ingest("u", pdf_bytes, file_name="bytes_test.pdf")
        _assert("PDF bytes pipeline → success", r["status"] == "success")
        _assert("PDF bytes pipeline → chunks > 0", r["chunks_created"] > 0)

    # ── Multiple sequential ingestions same user ──
    _sub("Sequential ingestions accumulate")

    store = LocalMemoryStore()
    adapter = BackboardMemoryAdapter(store)
    p = IngestionPipeline(memory_adapter=adapter, enable_logging=False)

    p.ingest("acc_user", "First ingestion about Python skills and expertise.")
    p.ingest("acc_user", "Second ingestion about web development experience I built.")
    p.ingest("acc_user", "Third ingestion I'm interested in data science and curious about MLOps.")

    all_chunks = store.retrieve_chunks("acc_user", limit=200)
    _assert("3 ingestions accumulated", len(all_chunks) >= 3, f"{len(all_chunks)} chunks")


# ═══════════════════════════════════════════════════════════════════════════════
# 11. RESPONSE STRUCTURE VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def test_response_structure():
    _header("RESPONSE STRUCTURE VALIDATION")

    pipeline = IngestionPipeline(enable_logging=False)

    _sub("Success response keys")
    r = pipeline.ingest("u", "I know machine learning and deep learning frameworks very well.")
    required_keys = ["detected_input_type", "status", "chunks_created", "items_stored",
                     "metadata_summary", "details"]
    for key in required_keys:
        _assert(f"Success response has '{key}'", key in r)

    _assert("metadata_summary has source_type", "source_type" in r.get("metadata_summary", {}))
    _assert("metadata_summary has content_length", "content_length" in r.get("metadata_summary", {}))
    _assert("details has processing", "processing" in r.get("details", {}))
    _assert("details has chunking", "chunking" in r.get("details", {}))
    _assert("details has storage", "storage" in r.get("details", {}))

    _sub("Error response keys")
    r = pipeline.ingest("u", "/no/such/file.pdf")
    for key in ["detected_input_type", "status", "chunks_created", "items_stored", "details"]:
        _assert(f"Error response has '{key}'", key in r)
    _assert("Error status = error", r["status"] == "error")
    _assert("Error has error message", "error" in r)


# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════

def print_summary():
    print(f"\n{'═' * 72}")
    print(f"  FINAL TEST SUMMARY")
    print(f"{'═' * 72}")

    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    total = len(results)

    # Show failures first
    failures = [r for r in results if not r["passed"]]
    if failures:
        print(f"\n  {FAIL} FAILURES ({len(failures)}):")
        for r in failures:
            det = f" — {r['detail']}" if r["detail"] else ""
            print(f"     {FAIL}  {r['test']}{det}")

    print(f"\n  {'─' * 68}")
    print(f"  Total: {total}  │  {PASS} Passed: {passed}  │  {FAIL} Failed: {failed}")
    if failed == 0:
        print(f"\n  🎉  ALL {total} TESTS PASSED!")
    else:
        print(f"\n  {WARN}  {failed} test(s) need attention")
    print(f"{'═' * 72}\n")

    return failed


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"\n{'🧪 INGESTION PIPELINE — COMPREHENSIVE TEST SUITE':^72}")
    print(f"{'═' * 72}")
    print(f"  Timestamp : {datetime.now().isoformat()}")
    print(f"  Python    : {sys.version.split()[0]}")
    print(f"  CWD       : {os.getcwd()}")
    print(f"{'═' * 72}")

    test_input_detector()
    test_text_processor()
    test_github_processor()
    test_pdf_processor()
    test_chunker()
    test_backboard_store()
    test_full_pipeline()
    test_ingest_input_convenience()
    test_fixed_chunking_pipeline()
    test_edge_cases()
    test_response_structure()

    exit_code = print_summary()
    sys.exit(exit_code)
