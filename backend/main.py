"""
FastAPI application entry point for Cortex backend.

Run with: uvicorn backend.main:app --reload --port 8000
"""

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.chatbot.router import router as chat_router
from backend.profile_scoring.router import router as profile_router

app = FastAPI(
    title="Cortex API",
    description="Backend API for Cortex knowledge visualization",
    version="1.0.0",
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",      # Next.js dev server
        "http://127.0.0.1:3000",
        "http://localhost:3001",      # Alternate port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount profile scoring routes
app.include_router(profile_router, prefix="/api")

# Mount chatbot routes
app.include_router(chat_router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Cortex API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
