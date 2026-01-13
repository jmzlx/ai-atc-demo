"""FastAPI application for AI ATC Demo.

Provides:
- Session listing and event retrieval for replay
- Health checks for services (OpenScope, MCP, LLM, V-JEPA)
- Screenshot proxy to MCP server
- Agent subprocess control (start/stop)
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .agent import agent_router, cleanup_agent
from .health import health_router
from .sessions import sessions_router

# Configuration
BASE_DIR = Path(__file__).parent.parent.resolve()
FRONTEND_URL = "http://localhost:5173"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - cleanup on shutdown."""
    yield
    # Cleanup agent subprocess if running
    await cleanup_agent()


app = FastAPI(
    title="AI ATC Demo API",
    description="Backend for live monitoring and session replay of AI ATC agent",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sessions_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(agent_router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint - API info."""
    return {
        "name": "AI ATC Demo API",
        "version": "0.2.0",
        "endpoints": {
            "sessions": "/api/sessions",
            "health": "/api/health",
            "screenshot": "/api/screenshot",
            "agent": "/api/agent/{start,stop,status}",
        },
    }
