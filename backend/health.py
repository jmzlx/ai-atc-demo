"""Health checks for services."""

import os

import httpx
from fastapi import APIRouter
from fastapi.responses import Response

health_router = APIRouter(tags=["health"])

# Service URLs (from environment or defaults)
OPENSCOPE_URL = os.getenv("OPENSCOPE_URL", "http://localhost:3003")
LLM_URL = os.getenv("LLM_URL", "http://localhost:1234/v1")
VJEPA_URL = os.getenv("VJEPA_URL", "http://localhost:8001")
MCP_URL = os.getenv("MCP_URL", "http://localhost:8080")


async def check_service(url: str, path: str = "", timeout: float = 2.0) -> bool:
    """Check if a service is running."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{url}{path}", timeout=timeout)
            return resp.status_code == 200
    except (httpx.RequestError, httpx.HTTPStatusError):
        return False


async def check_vjepa() -> bool:
    """Check V-JEPA health endpoint."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{VJEPA_URL}/health", timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("status") == "healthy"
            return False
    except (httpx.RequestError, httpx.HTTPStatusError):
        return False


@health_router.get("/health")
async def health_check():
    """Check health of all services."""
    openscope_ok = await check_service(OPENSCOPE_URL)
    mcp_ok = await check_service(MCP_URL, "/health")
    llm_ok = await check_service(LLM_URL, "/models")
    vjepa_ok = await check_vjepa()

    return {
        "openscope": {"url": OPENSCOPE_URL, "status": "running" if openscope_ok else "offline"},
        "mcp": {"url": MCP_URL, "status": "running" if mcp_ok else "offline"},
        "llm": {"url": LLM_URL, "status": "running" if llm_ok else "offline"},
        "vjepa": {"url": VJEPA_URL, "status": "running" if vjepa_ok else "offline"},
    }


@health_router.get("/screenshot")
async def get_screenshot():
    """Proxy screenshot from MCP server."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{MCP_URL}/screenshot", timeout=5.0)
            if resp.status_code == 200:
                return Response(
                    content=resp.content,
                    media_type=resp.headers.get("content-type", "image/png"),
                )
            return Response(status_code=resp.status_code, content=b"")
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        return Response(status_code=503, content=f"MCP unavailable: {e}".encode())
