"""
Comprehensive examples and integration tests for the ingestion pipeline.
Demonstrates all major features and integration patterns.
"""

import os
from pathlib import Path
from ingestion import (
    IngestionPipeline,
    ingest_input,
    BackboardMemoryAdapter,
    LocalMemoryStore,
    TextPromptProcessor,
    GitHubProcessor,
    PDFProcessor,
    SemanticChunker,
)


def example_1_text_prompt_basic():
    """Example 1: Simple text prompt ingestion"""
    print("\n" + "="*70)
    print("EXAMPLE 1: TEXT PROMPT - BASIC INGESTION")
    print("="*70)
    
    # Simple function call
    result = ingest_input(
        user_id="user_001",
        input_data="I'm skilled in Python and JavaScript. "
                   "I have experience building web applications with React."
    )
    
    print(f"\nInput Type: {result['detected_input_type']}")
    print(f"Status: {result['status']}")
    print(f"Chunks Created: {result['chunks_created']}")
    print(f"Items Stored: {result['items_stored']}")
    
    metadata = result.get('metadata_summary', {})
    print(f"\nMetadata:")
    print(f"  Category: {metadata.get('category')}")
    print(f"  Content Length: {metadata.get('content_length')} chars")
    print(f"  Word Count: {metadata.get('word_count')}")


def example_2_text_categories():
    """Example 2: Text prompt with different categories"""
    print("\n" + "="*70)
    print("EXAMPLE 2: TEXT PROMPT - CATEGORY INFERENCE")
    print("="*70)
    
    test_cases = [
        ("skill", "I'm proficient in machine learning and deep learning using TensorFlow."),
        ("interest", "I'm very interested in renewable energy and sustainable technology."),
        ("experience", "I led a team of 5 engineers to build a microservices architecture."),
        ("project_idea", "I'm thinking about building an AI-powered recommendation system."),
        ("preference", "I prefer working with TypeScript and hate JavaScript's flexibility."),
    ]
    
    pipeline = IngestionPipeline(enable_logging=False)
    
    for expected_category, text in test_cases:
        result = pipeline.ingest("test_user", text)
        metadata = result.get('metadata_summary', {})
        category = metadata.get('category')
        
        print(f"\nText: {text[:50]}...")
        print(f"Expected: {expected_category:15} | Detected: {category:15}")
        print(f"Chunks: {result['chunks_created']}")


def example_3_github_repo_processing():
    """Example 3: GitHub repository ingestion"""
    print("\n" + "="*70)
    print("EXAMPLE 3: GITHUB REPOSITORY INGESTION")
    print("="*70)
    
    github_url = "https://github.com/openai/gpt-3"
    
    print(f"\nIngesting GitHub repository: {github_url}")
    print("Note: This requires a valid GitHub token for API access.")
    print("Set GITHUB_TOKEN environment variable to enable.")
    
    # Create processor to demonstrate URL validation
    processor = GitHubProcessor()
    validation = processor._validate_repo_url(github_url)
    
    if validation['is_valid']:
        print(f"\n✓ URL is valid")
        print(f"  Owner: {validation['owner']}")
        print(f"  Repository: {validation['repo']}")
    else:
        print(f"\n✗ URL validation failed: {validation.get('error')}")
    
    # To actually ingest (requires API):
    # result = ingest_input("user_002", github_url)
    # print(f"\nStatus: {result['status']}")
    # print(f"Languages: {result['details']['storage'].get('languages', [])}")


def example_4_pdf_processing():
    """Example 4: PDF document ingestion"""
    print("\n" + "="*70)
    print("EXAMPLE 4: PDF DOCUMENT INGESTION")
    print("="*70)
    
    print("\nPDF Processing Example:")
    print("Note: Requires an actual PDF file to demonstrate.")
    print("\nUsage:")
    print("  result = ingest_input('user_id', '/path/to/document.pdf')")
    
    # Demonstrate PDF processor validation
    pdf_processor = PDFProcessor()
    
    test_paths = [
        "/path/to/document.pdf",
        "/path/to/image.jpg",
        "/nonexistent/file.pdf",
    ]
    
    for path in test_paths:
        validation = pdf_processor._validate_pdf_file(path)
        status = "✓ Valid" if validation['is_valid'] else "✗ Invalid"
        error = validation.get('error', 'No error')
        print(f"\n{path}")
        print(f"  {status}")
        if not validation['is_valid']:
            print(f"  Error: {error}")


def example_5_custom_chunking():
    """Example 5: Custom chunking strategies"""
    print("\n" + "="*70)
    print("EXAMPLE 5: CUSTOM CHUNKING STRATEGIES")
    print("="*70)
    
    long_text = """
    Artificial Intelligence is transforming the world.
    Machine learning enables systems to learn from data.
    Deep learning uses neural networks with multiple layers.
    
    Natural Language Processing helps computers understand human language.
    Computer Vision allows machines to interpret images and video.
    Reinforcement Learning trains agents through rewards and penalties.
    
    AI applications span healthcare, finance, transportation, and education.
    Ethical considerations are crucial for responsible AI development.
    The future of AI involves integration with other technologies.
    """
    
    metadata = {"user_id": "user_003", "source": "example"}
    
    # Semantic chunking
    print("\nSemantic Chunking (default):")
    semantic_chunker = SemanticChunker(target_size=200, overlap=50)
    chunks = semantic_chunker.chunk(long_text, metadata)
    
    print(f"  Total chunks: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i}: {len(chunk.content)} chars | {len(chunk.content.split())} words")
    
    # Fixed-size chunking
    print("\nFixed-Size Chunking:")
    from ingestion import FixedSizeChunker
    
    fixed_chunker = FixedSizeChunker(chunk_size=200, overlap=50)
    chunks = fixed_chunker.chunk(long_text, metadata)
    
    print(f"  Total chunks: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i}: {len(chunk.content)} chars | {len(chunk.content.split())} words")


def example_6_backboard_storage():
    """Example 6: Backboard storage and retrieval"""
    print("\n" + "="*70)
    print("EXAMPLE 6: BACKBOARD STORAGE")
    print("="*70)
    
    # Use local store for demo (no API required)
    local_store = LocalMemoryStore()
    adapter = BackboardMemoryAdapter(local_store)
    
    print("\nStoring chunks in local memory (demo mode)...")
    
    # Create some test chunks
    chunks = [
        {
            "content": "Python is a powerful programming language",
            "metadata": {"user_id": "user_004"}
        },
        {
            "content": "JavaScript runs in the browser",
            "metadata": {"user_id": "user_004"}
        },
        {
            "content": "React is a JavaScript library for building UIs",
            "metadata": {"user_id": "user_004"}
        },
    ]
    
    # Store
    result = adapter.save_ingestion_result(
        user_id="user_004",
        input_type="text_prompt",
        chunks=chunks,
        metadata={"category": "programming"}
    )
    
    print(f"\nStorage Result:")
    print(f"  Success: {result['success']}")
    print(f"  Stored: {result['stored_count']} chunks")
    print(f"  IDs: {result['chunk_ids']}")
    
    # Retrieve
    print(f"\nRetrieving chunks...")
    retrieved = adapter.search_memories(
        user_id="user_004",
        query="programming",
        limit=10
    )
    
    print(f"  Retrieved: {len(retrieved)} chunks")
    for i, chunk in enumerate(retrieved):
        content = chunk.get("content", "")[:50]
        print(f"  {i+1}. {content}...")


def example_7_pipeline_integration():
    """Example 7: Full pipeline integration example"""
    print("\n" + "="*70)
    print("EXAMPLE 7: FULL PIPELINE INTEGRATION")
    print("="*70)
    
    # Initialize pipeline with local storage
    local_store = LocalMemoryStore()
    adapter = BackboardMemoryAdapter(local_store)
    pipeline = IngestionPipeline(
        memory_adapter=adapter,
        chunking_strategy="semantic",
        enable_logging=True
    )
    
    # Simulate ingesting multiple items for one user
    user_id = "user_005"
    inputs = [
        ("I'm skilled in Python, JavaScript, and React", "skill"),
        ("Interested in machine learning and AI", "interest"),
        ("Built a web scraper and data pipeline", "experience"),
    ]
    
    print(f"\nIngesting {len(inputs)} items for user: {user_id}\n")
    
    results = []
    for text, expected_category in inputs:
        result = pipeline.ingest(user_id, text)
        results.append(result)
        
        print(f"✓ {text[:40]}...")
        print(f"  Type: {result['detected_input_type']}")
        print(f"  Category: {result['metadata_summary'].get('category')}")
        print(f"  Chunks: {result['chunks_created']}\n")
    
    # Search memories
    print(f"\nSearching memories for user {user_id}...")
    memories = adapter.search_memories(user_id, "python", limit=5)
    print(f"Found {len(memories)} relevant memories")


def example_8_error_handling():
    """Example 8: Error handling and edge cases"""
    print("\n" + "="*70)
    print("EXAMPLE 8: ERROR HANDLING")
    print("="*70)
    
    pipeline = IngestionPipeline(enable_logging=False)
    
    # Test cases
    test_cases = [
        ("", "Empty string"),
        ("   ", "Only whitespace"),
        ("a", "Too short"),
        ("https://invalid-github.com/user/repo", "Invalid GitHub URL"),
        ("not a url or text\n@#$%", "Gibberish"),
    ]
    
    print("\nTesting error handling:\n")
    
    for test_input, description in test_cases:
        result = pipeline.ingest("test_user", test_input)
        status = "✓" if result['status'] == 'success' else "✗"
        
        print(f"{status} {description}")
        if result['status'] == 'error':
            print(f"   Error: {result.get('error', 'Unknown')}")
        else:
            print(f"   Chunks: {result['chunks_created']}")


def example_9_fastapi_integration():
    """Example 9: FastAPI integration pattern"""
    print("\n" + "="*70)
    print("EXAMPLE 9: FASTAPI INTEGRATION")
    print("="*70)
    
    code = '''
# backend/routes/ingestion.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from backend.ingestion import IngestionPipeline

app = FastAPI()
pipeline = IngestionPipeline()

@app.post("/api/ingest/text")
async def ingest_text(user_id: str, text: str):
    """Ingest plain text input"""
    result = pipeline.ingest(user_id, text)
    if result['status'] == 'error':
        raise HTTPException(status_code=400, detail=result.get('error'))
    return result

@app.post("/api/ingest/github")
async def ingest_github(user_id: str, repo_url: str):
    """Ingest GitHub repository"""
    result = pipeline.ingest(user_id, repo_url)
    if result['status'] == 'error':
        raise HTTPException(status_code=400, detail=result.get('error'))
    return result

@app.post("/api/ingest/pdf")
async def ingest_pdf(user_id: str, file: UploadFile = File(...)):
    """Ingest PDF document"""
    content = await file.read()
    result = pipeline.ingest(user_id, content, file.filename)
    if result['status'] == 'error':
        raise HTTPException(status_code=400, detail=result.get('error'))
    return result

@app.get("/api/search")
async def search_memories(user_id: str, query: str, source_type: str = None):
    """Search user memories"""
    from backend.ingestion import BackboardMemoryAdapter
    adapter = BackboardMemoryAdapter()
    return adapter.search_memories(user_id, query, source_type, limit=10)
    '''
    
    print("\nExample FastAPI integration:\n")
    print(code)


def run_all_examples():
    """Run all examples"""
    print("\n\n")
    print("█" * 70)
    print("█" + " " * 68 + "█")
    print("█" + "  INGESTION PIPELINE - COMPREHENSIVE EXAMPLES".center(68) + "█")
    print("█" + " " * 68 + "█")
    print("█" * 70)
    
    example_1_text_prompt_basic()
    example_2_text_categories()
    example_3_github_repo_processing()
    example_4_pdf_processing()
    example_5_custom_chunking()
    example_6_backboard_storage()
    example_7_pipeline_integration()
    example_8_error_handling()
    example_9_fastapi_integration()
    
    print("\n\n")
    print("█" * 70)
    print("█" + "  ALL EXAMPLES COMPLETED SUCCESSFULLY".center(68) + "█")
    print("█" * 70)
    print("\n")


if __name__ == "__main__":
    run_all_examples()
