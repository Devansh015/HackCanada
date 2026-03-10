"""
Main ingestion pipeline.
Orchestrates input detection, processing, chunking, and storage in Backboard.
"""

import os
from typing import Dict, Any, Optional, Union
from pathlib import Path
import logging

# Load .env — walk upward to find it (works locally & on Railway)
try:
    from dotenv import load_dotenv
    _p = Path(__file__).resolve().parent
    while _p != _p.parent:
        if (_p / ".env").exists():
            load_dotenv(_p / ".env")
            break
        _p = _p.parent
except ImportError:
    pass

from .input_detector import detect_input_type
from .text_processor import TextPromptProcessor
from .github_processor import GitHubProcessor
from .pdf_processor import PDFProcessor
from .chunker import SemanticChunker, create_chunker
from .backboard_client import BackboardMemoryAdapter, BackboardAPIClient, LocalMemoryStore

# Profile scoring integration (optional – gracefully skipped if unavailable)
try:
    from profile_scoring.orchestrator import update_profile_from_upload as _score_upload
    _HAS_PROFILE_SCORING = True
except ImportError:
    _HAS_PROFILE_SCORING = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Main ingestion pipeline for processing user inputs.
    
    Automatically detects input type and routes through appropriate processors.
    """
    
    def __init__(
        self,
        memory_adapter: Optional[BackboardMemoryAdapter] = None,
        chunking_strategy: str = "semantic",
        enable_logging: bool = True,
    ):
        """
        Initialize the ingestion pipeline.
        
        Args:
            memory_adapter: Backboard memory adapter (uses local if None)
            chunking_strategy: "semantic" or "fixed"
            enable_logging: Whether to log pipeline steps
        """
        # Initialize memory adapter
        if memory_adapter is None:
            # Auto-detect: use real Backboard.io if env vars are set,
            # otherwise fall back to local in-memory store.
            memory_adapter = BackboardMemoryAdapter()  # handles fallback internally
        self.memory_adapter = memory_adapter
        self.enable_logging = enable_logging
        
        self._log(
            f"Memory backend: {'Backboard.io API' if self.memory_adapter.is_live else 'LocalMemoryStore'}"
        )
        
        # Initialize processors
        self.text_processor = TextPromptProcessor()
        self.github_processor = GitHubProcessor()
        self.pdf_processor = PDFProcessor()
        
        # Initialize chunker
        self.chunker = create_chunker(chunking_strategy)
    
    def ingest(
        self,
        user_id: str,
        input_data: Union[str, bytes, Path],
        file_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Main ingestion function. Automatically detects input type and processes.
        
        Args:
            user_id: User ID for tracking and memory association
            input_data: The input (text, GitHub URL, PDF file, etc.)
            file_name: Optional filename (used for PDF uploads)
        
        Returns:
            Dict with ingestion results:
            - detected_input_type: Type of input detected
            - status: "success" or "error"
            - chunks_created: Number of chunks created
            - items_stored: Number of items stored in Backboard
            - metadata_summary: Summary of stored metadata
            - details: Full processing details
        """
        
        self._log(f"Starting ingestion for user {user_id}")
        
        # Step 1: Detect input type
        detection = detect_input_type(input_data)
        detected_type = detection["detected_type"]
        
        self._log(f"Detected input type: {detected_type}")
        
        if not detection["is_valid"]:
            return self._error_response(
                detected_type,
                f"Invalid input: {detection['metadata'].get('error', 'Unknown error')}",
            )
        
        try:
            # Step 2: Route to appropriate processor
            processing_result = self._process_by_type(
                detected_type,
                input_data,
                file_name,
                user_id,
            )
            
            if not processing_result.get("success"):
                return self._error_response(
                    detected_type,
                    processing_result.get("error", "Processing failed"),
                )
            
            processed_content = processing_result["content"]
            processed_metadata = processing_result["metadata"]
            
            self._log(f"Processing complete. Content length: {len(processed_content)}")
            
            # Step 3: Chunk the content
            chunking_result = self._chunk_content(
                processed_content,
                processed_metadata,
            )
            
            chunks = chunking_result["chunks"]
            chunk_dicts = [chunk.to_dict() for chunk in chunks]
            
            self._log(f"Created {len(chunks)} chunks")
            
            # Step 4: Store in Backboard
            storage_result = self.memory_adapter.save_ingestion_result(
                user_id=user_id,
                input_type=detected_type,
                chunks=chunk_dicts,
                metadata=processed_metadata,
            )
            
            self._log(f"Stored {storage_result.get('stored_count', 0)} chunks in Backboard")
            
            # Step 5: Profile scoring (auto-update user knowledge profile)
            profile_update = None
            if _HAS_PROFILE_SCORING:
                try:
                    self._log("Running profile scoring via Gemini…")
                    profile_update = _score_upload(
                        user_id=user_id,
                        source_type=detected_type,
                        content=processed_content,
                    )
                    if profile_update.get("success"):
                        n_changed = len(
                            profile_update.get("summary", {}).get("categories_increased", [])
                        )
                        self._log(f"Profile updated – {n_changed} categories changed")
                    else:
                        self._log(f"Profile scoring returned error: {profile_update.get('error')}")
                except Exception as e:
                    logger.warning(f"Profile scoring failed (non-fatal): {e}")
                    profile_update = {"success": False, "error": str(e)}
            
            # Step 6: Return success response
            return {
                "detected_input_type": detected_type,
                "status": "success",
                "chunks_created": len(chunks),
                "items_stored": storage_result.get("stored_count", 0),
                "metadata_summary": {
                    "source_type": processed_metadata.get("source_type"),
                    "category": processed_metadata.get("category"),
                    "content_length": len(processed_content),
                    "word_count": len(processed_content.split()),
                    "timestamp": processed_metadata.get("timestamp"),
                },
                "details": {
                    "processing": processing_result,
                    "chunking": chunking_result,
                    "storage": storage_result,
                    "profile_update": profile_update,
                },
            }
        
        except Exception as e:
            logger.exception(f"Ingestion pipeline error: {e}")
            return self._error_response(detected_type, str(e))
    
    def _process_by_type(
        self,
        input_type: str,
        input_data: any,
        file_name: Optional[str],
        user_id: str,
    ) -> Dict[str, Any]:
        """Route to appropriate processor based on input type."""
        
        try:
            if input_type == "text_prompt":
                result = self.text_processor.process(input_data, user_id)
                return {
                    "success": True,
                    "content": result["content"],
                    "metadata": result["metadata"],
                }
            
            elif input_type == "github_repo":
                result = self.github_processor.process(input_data, user_id)
                if not result["validation"]["is_valid"]:
                    return {
                        "success": False,
                        "error": result["metadata"].get("error", "GitHub processing failed"),
                    }
                # Also check for API-level errors (e.g. rate-limited, repo not found)
                if result["metadata"].get("error"):
                    return {
                        "success": False,
                        "error": result["metadata"]["error"],
                    }
                if not result["content"]:
                    return {
                        "success": False,
                        "error": "No content could be fetched from this GitHub repository.",
                    }
                return {
                    "success": True,
                    "content": result["content"],
                    "metadata": result["metadata"],
                }
            
            elif input_type == "pdf":
                result = self.pdf_processor.process(input_data, user_id, file_name)
                if result["metadata"].get("error"):
                    return {
                        "success": False,
                        "error": result["metadata"].get("error", "PDF processing failed"),
                    }
                return {
                    "success": True,
                    "content": result["content"],
                    "metadata": result["metadata"],
                }
            
            else:
                return {
                    "success": False,
                    "error": f"Unsupported input type: {input_type}",
                }
        
        except Exception as e:
            logger.exception(f"Processing error for type {input_type}: {e}")
            return {
                "success": False,
                "error": f"Processing error: {str(e)}",
            }
    
    def _chunk_content(
        self,
        content: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Chunk the processed content."""
        
        try:
            chunks = self.chunker.chunk(content, metadata)
            
            return {
                "success": True,
                "chunks": chunks,
                "chunk_count": len(chunks),
                "total_chars": sum(len(c.content) for c in chunks),
            }
        
        except Exception as e:
            logger.exception(f"Chunking error: {e}")
            return {
                "success": False,
                "error": str(e),
                "chunks": [],
            }
    
    def _log(self, message: str) -> None:
        """Log a message if logging is enabled."""
        if self.enable_logging:
            logger.info(message)
    
    def _error_response(self, input_type: str, error: str) -> Dict[str, Any]:
        """Generate a standardized error response."""
        return {
            "detected_input_type": input_type,
            "status": "error",
            "error": error,
            "chunks_created": 0,
            "items_stored": 0,
            "metadata_summary": {},
            "details": {
                "error": error,
            },
        }


# Convenience function for simple usage
def ingest_input(
    user_id: str,
    input_data: Union[str, bytes, Path],
    file_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Simple ingestion function using default pipeline.
    
    Args:
        user_id: User ID
        input_data: Input to ingest
        file_name: Optional filename
    
    Returns:
        Ingestion result
    """
    pipeline = IngestionPipeline()
    return pipeline.ingest(user_id, input_data, file_name)


# Example usage and testing
if __name__ == "__main__":
    # Initialize pipeline with local storage for demo
    pipeline = IngestionPipeline(enable_logging=True)
    
    print("=" * 60)
    print("Ingestion Pipeline Examples")
    print("=" * 60)
    
    # Example 1: Text prompt ingestion
    print("\n1. TEXT PROMPT INGESTION")
    print("-" * 60)
    
    text_input = "I'm skilled in Python and machine learning. Recently built a recommendation system."
    result = pipeline.ingest("user_001", text_input)
    
    print(f"Status: {result['status']}")
    print(f"Type: {result['detected_input_type']}")
    print(f"Chunks: {result['chunks_created']}")
    print(f"Stored: {result['items_stored']}")
    if result.get('metadata_summary'):
        print(f"Category: {result['metadata_summary'].get('category')}")
    
    # Example 2: GitHub repo ingestion (would need working GitHub API)
    print("\n2. GITHUB REPOSITORY INGESTION")
    print("-" * 60)
    
    github_url = "https://github.com/openai/gpt-3"
    print(f"Input: {github_url}")
    # Uncomment to actually ingest:
    # result = pipeline.ingest("user_002", github_url)
    # print(f"Status: {result['status']}")
    # print(f"Chunks: {result['chunks_created']}")
    
    # Example 3: PDF ingestion (would need actual PDF file)
    print("\n3. PDF INGESTION")
    print("-" * 60)
    
    pdf_path = "/path/to/document.pdf"
    print(f"Would ingest PDF from: {pdf_path}")
    # result = pipeline.ingest("user_003", pdf_path)
    
    print("\n" + "=" * 60)
    print("Pipeline examples complete!")
    print("=" * 60)
