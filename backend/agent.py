"""Agent subprocess control - start/stop the ATC agent."""

import asyncio
import os
import subprocess
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

agent_router = APIRouter(tags=["agent"])

# Paths
BASE_DIR = Path(__file__).parent.parent.resolve()
AGENT_CWD = (BASE_DIR.parent / "openscope-llm-agent").resolve()
MCP_CWD = (BASE_DIR.parent / "mcp-openscope").resolve()

# Configuration
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))
MCP_URL = os.getenv("MCP_URL", f"http://localhost:{MCP_PORT}")

# Process state
_mcp_proc: subprocess.Popen | None = None
_agent_proc: subprocess.Popen | None = None
_session_id: str | None = None


class AgentStartRequest(BaseModel):
    """Request to start the agent."""

    timewarp: int = 10
    cycles: int = 100
    model: str | None = None
    base_url: str | None = None
    airport: str | None = None


class AgentStatus(BaseModel):
    """Agent status response."""

    running: bool
    session_id: str | None = None
    mcp_running: bool = False


async def start_mcp() -> subprocess.Popen:
    """Start the MCP server in HTTP mode."""
    global _mcp_proc

    if not MCP_CWD.exists():
        raise HTTPException(status_code=500, detail=f"MCP directory not found: {MCP_CWD}")

    cmd = [
        "uv",
        "run",
        "python",
        "-m",
        "mcp_openscope",
        "--http",
        "--port",
        str(MCP_PORT),
    ]

    _mcp_proc = subprocess.Popen(
        cmd,
        cwd=MCP_CWD,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for MCP to be ready (up to 15 seconds)
    import httpx

    for _ in range(30):
        await asyncio.sleep(0.5)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{MCP_URL}/health", timeout=2.0)
                if resp.status_code == 200:
                    return _mcp_proc
        except Exception:
            pass
        if _mcp_proc.poll() is not None:
            raise HTTPException(status_code=500, detail="MCP server exited unexpectedly")

    _mcp_proc.kill()
    _mcp_proc.wait()
    _mcp_proc = None
    raise HTTPException(status_code=500, detail="MCP server did not become ready")


def stop_mcp():
    """Stop the MCP server."""
    global _mcp_proc
    if _mcp_proc and _mcp_proc.poll() is None:
        _mcp_proc.terminate()
        try:
            _mcp_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _mcp_proc.kill()
    _mcp_proc = None


def start_agent_subprocess(request: AgentStartRequest) -> tuple[subprocess.Popen, str]:
    """Start the agent subprocess."""
    global _agent_proc, _session_id
    from datetime import datetime

    if not AGENT_CWD.exists():
        raise HTTPException(status_code=500, detail=f"Agent directory not found: {AGENT_CWD}")

    # Use same session ID format as agent: atc_YYYYMMDD_HHMMSS
    session_id = f"atc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    cmd = [
        "uv",
        "run",
        "python",
        "-m",
        "openscope_llm_agent",
        "--headless",
        "--mcp-url",
        MCP_URL,
        "--cycles",
        str(request.cycles),
        "--timewarp",
        str(request.timewarp),
        "--session",
        session_id,
    ]

    if request.model:
        cmd.extend(["--model", request.model])
    if request.base_url:
        cmd.extend(["--base-url", request.base_url])
    if request.airport:
        cmd.extend(["--airport", request.airport])

    _agent_proc = subprocess.Popen(
        cmd,
        cwd=AGENT_CWD,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    _session_id = session_id
    return _agent_proc, session_id


def stop_agent_subprocess():
    """Stop the agent subprocess."""
    global _agent_proc, _session_id
    if _agent_proc and _agent_proc.poll() is None:
        _agent_proc.terminate()
        try:
            _agent_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _agent_proc.kill()
    _agent_proc = None
    _session_id = None


async def cleanup_agent():
    """Cleanup function for application shutdown."""
    stop_agent_subprocess()
    stop_mcp()


@agent_router.post("/agent/start")
async def start_agent(request: AgentStartRequest):
    """Start the ATC agent."""
    global _mcp_proc, _agent_proc

    if _agent_proc and _agent_proc.poll() is None:
        raise HTTPException(status_code=400, detail="Agent already running")

    # Start MCP server if not running
    if not _mcp_proc or _mcp_proc.poll() is not None:
        await start_mcp()
        await asyncio.sleep(1)  # Allow MCP to fully initialize

    # Start agent
    proc, session_id = start_agent_subprocess(request)

    return {"status": "started", "session_id": session_id}


@agent_router.post("/agent/stop")
async def stop_agent():
    """Stop the ATC agent."""
    stop_agent_subprocess()
    stop_mcp()
    return {"status": "stopped"}


@agent_router.get("/agent/status", response_model=AgentStatus)
async def agent_status():
    """Get agent status."""
    agent_running = _agent_proc is not None and _agent_proc.poll() is None
    mcp_running = _mcp_proc is not None and _mcp_proc.poll() is None

    return AgentStatus(
        running=agent_running,
        session_id=_session_id if agent_running else None,
        mcp_running=mcp_running,
    )
