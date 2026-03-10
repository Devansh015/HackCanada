"""
FastAPI application entry point for Cortex backend.

Run locally:  uvicorn main:app --reload --port 8000
Deploy:       Railway reads Procfile / railway.toml automatically.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chatbot.router import router as chat_router
from profile_scoring.router import router as profile_router

app = FastAPI(
    title="Cortex API",
    description="Backend API for Cortex knowledge visualization",
    version="1.0.0",
)

# CORS — allow frontend origins from env or fall back to localhost defaults
_default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
]
_env_origins = os.getenv("CORS_ORIGINS", "")
cors_origins = [o.strip() for o in _env_origins.split(",") if o.strip()] if _env_origins else _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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
