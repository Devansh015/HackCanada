"""
FastAPI application entry point for Lumas backend.

Run with: uvicorn backend.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.profile_scoring.router import router as profile_router

app = FastAPI(
    title="Lumas API",
    description="Backend API for Lumas knowledge visualization",
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

@app.get("/")
async def root():
    return {"message": "Lumas API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
