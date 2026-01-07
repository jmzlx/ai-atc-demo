"""AI ATC Demo Interface - Streamlit App.

A simple demo interface for live demonstrations of the AI ATC agent system.
Run with: uv run streamlit run app.py
"""

import atexit
import json
import os
import subprocess
import time
from pathlib import Path

import httpx
import streamlit as st
from dotenv import load_dotenv


# =============================================================================
# CLEANUP (registered before session_state to ensure it runs)
# =============================================================================

def _cleanup_processes():
    """Clean up any running subprocesses on exit."""
    if hasattr(st, "session_state"):
        if st.session_state.get("agent_proc"):
            try:
                st.session_state.agent_proc.terminate()
                st.session_state.agent_proc.wait(timeout=2)
            except Exception:
                try:
                    st.session_state.agent_proc.kill()
                except Exception:
                    pass
        if st.session_state.get("mcp_proc"):
            try:
                st.session_state.mcp_proc.terminate()
                st.session_state.mcp_proc.wait(timeout=2)
            except Exception:
                try:
                    st.session_state.mcp_proc.kill()
                except Exception:
                    pass

atexit.register(_cleanup_processes)

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# CONFIGURATION (from .env with sensible defaults)
# =============================================================================

# Base directory for resolving relative paths
BASE_DIR = Path(__file__).parent.resolve()

OPENSCOPE_URL = os.getenv("OPENSCOPE_URL", "http://localhost:3003")
LLM_URL = os.getenv("LLM_URL", "http://localhost:1234/v1")
VJEPA_URL = os.getenv("VJEPA_URL", "http://localhost:8001")

# MCP configuration - extract port for consistency
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))
MCP_URL = os.getenv("MCP_URL", f"http://localhost:{MCP_PORT}")

# Paths with defaults (relative to this directory)
MCP_CWD = (BASE_DIR / os.getenv("MCP_CWD", "../mcp-openscope")).resolve()
AGENT_CWD = (BASE_DIR / os.getenv("AGENT_CWD", "../openscope-llm-agent")).resolve()

AGENT_MODULE = "openscope_llm_agent.agent.runner"
LOG_DIR = BASE_DIR / "logs"


# =============================================================================
# HEALTH CHECKS
# =============================================================================


def check_openscope() -> bool:
    """Check if OpenScope is running at localhost:3003."""
    try:
        resp = httpx.get(OPENSCOPE_URL, timeout=2.0)
        return resp.status_code == 200
    except (httpx.RequestError, httpx.HTTPStatusError):
        return False


def check_llm() -> bool:
    """Check if LLM server is running at localhost:1234."""
    try:
        resp = httpx.get(f"{LLM_URL}/models", timeout=2.0)
        return resp.status_code == 200
    except (httpx.RequestError, httpx.HTTPStatusError):
        return False


def check_vjepa() -> bool:
    """Check if V-JEPA server is running at localhost:8001."""
    try:
        resp = httpx.get(f"{VJEPA_URL}/health", timeout=2.0)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("status") == "healthy"
        return False
    except (httpx.RequestError, httpx.HTTPStatusError):
        return False


def check_mcp() -> bool:
    """Check if MCP server is running in HTTP mode."""
    try:
        resp = httpx.get(f"{MCP_URL}/health", timeout=2.0)
        return resp.status_code == 200
    except (httpx.RequestError, httpx.HTTPStatusError):
        return False


# =============================================================================
# MCP SERVER CONTROL
# =============================================================================


def start_mcp() -> subprocess.Popen:
    """Start the MCP server in HTTP mode.

    Returns:
        subprocess.Popen: MCP server process

    Raises:
        FileNotFoundError: If MCP directory doesn't exist
    """
    if not MCP_CWD.exists():
        raise FileNotFoundError(f"MCP directory not found: {MCP_CWD}")

    cmd = [
        "uv", "run", "python", "-m", "mcp_openscope",
        "--http",
        "--port", str(MCP_PORT),
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=MCP_CWD,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for MCP to be ready (up to 10 seconds)
    for _ in range(20):
        time.sleep(0.5)
        if check_mcp():
            return proc
        if proc.poll() is not None:
            raise RuntimeError("MCP server exited unexpectedly")

    proc.kill()
    proc.wait()  # Ensure process is fully terminated
    raise RuntimeError("MCP server did not become ready in 10 seconds")


def stop_mcp(proc: subprocess.Popen) -> None:
    """Stop the MCP server process."""
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def fetch_screenshot() -> bytes | None:
    """Fetch screenshot from MCP server.

    Returns:
        Raw PNG bytes, or None if failed
    """
    try:
        resp = httpx.get(f"{MCP_URL}/screenshot", timeout=5.0)
        if resp.status_code == 200:
            return resp.content
        return None
    except (httpx.RequestError, httpx.HTTPStatusError):
        return None


# =============================================================================
# AGENT CONTROL
# =============================================================================


def start_agent(timewarp: int = 10) -> tuple[subprocess.Popen, str]:
    """Start the agent subprocess connected to MCP HTTP server.

    Args:
        timewarp: Game speed multiplier (1-50)

    Raises:
        FileNotFoundError: If agent directory doesn't exist
        RuntimeError: If agent fails to start
    """
    if not AGENT_CWD.exists():
        raise FileNotFoundError(f"Agent directory not found: {AGENT_CWD}")

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Generate a simple session ID based on timestamp
    session_id = f"demo_{int(time.time())}"
    log_subdir = LOG_DIR / session_id
    log_subdir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "uv", "run", "python", "-m", AGENT_MODULE,
        "--auto-execute",
        "--headless",  # Run browser headless - demo shows screenshots
        "--mcp-url", MCP_URL,  # Connect to HTTP server instead of spawning stdio
        "--log-dir", str(log_subdir.resolve()),
        "--max-iterations", "200",
        "--loop-delay", "0.5",
        "--timewarp", str(timewarp),
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=AGENT_CWD,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return proc, session_id


def stop_agent(proc: subprocess.Popen) -> None:
    """Stop the agent subprocess."""
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


# =============================================================================
# EVENT READING
# =============================================================================


def find_events_file(session_id: str) -> Path | None:
    """Find the events JSONL file for a session."""
    log_subdir = LOG_DIR / session_id
    if not log_subdir.exists():
        return None

    # Look for events_*.jsonl files
    event_files = list(log_subdir.glob("events_*.jsonl"))
    if event_files:
        return event_files[0]
    return None


def read_events(session_id: str) -> list[dict]:
    """Read all events from the session's JSONL file."""
    events_file = find_events_file(session_id)
    if not events_file or not events_file.exists():
        return []

    events = []
    with open(events_file) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events


def get_decisions(events: list[dict]) -> list[dict]:
    """Extract decision events with their outcomes."""
    decisions = []
    outcomes = {e["correlation_id"]: e for e in events if e.get("event_type") == "outcome"}

    for event in events:
        if event.get("event_type") == "decision":
            outcome = outcomes.get(event.get("correlation_id"), {})
            decisions.append({
                "callsign": event.get("callsign", "???"),
                "command": f"{event.get('command_type', '???').upper()} {event.get('command_value', '')}",
                "success": outcome.get("success", None),
                "error": outcome.get("error", ""),
            })

    return decisions


def get_metrics(events: list[dict]) -> dict:
    """Compute metrics from events."""
    landings = sum(1 for e in events if e.get("event_type") == "landing")
    decisions = [e for e in events if e.get("event_type") == "decision"]
    outcomes = [e for e in events if e.get("event_type") == "outcome"]

    successes = sum(1 for e in outcomes if e.get("success"))
    success_rate = (successes / len(outcomes) * 100) if outcomes else 0

    # Get latest score from state snapshots
    snapshots = [e for e in events if e.get("event_type") == "state_snapshot"]
    score = snapshots[-1].get("score", 0) if snapshots else 0

    # Count conflicts detected
    conflicts = sum(1 for e in events if e.get("event_type") == "conflict_detected")

    return {
        "landings": landings,
        "decisions": len(decisions),
        "success_rate": success_rate,
        "score": score,
        "conflicts": conflicts,
    }


# =============================================================================
# STREAMLIT UI
# =============================================================================

st.set_page_config(page_title="AI ATC Demo", layout="wide")
st.title("AI ATC Demo")

# Initialize session state
if "agent_proc" not in st.session_state:
    st.session_state.agent_proc = None
if "mcp_proc" not in st.session_state:
    st.session_state.mcp_proc = None
if "session_id" not in st.session_state:
    st.session_state.session_id = None

# --- Health Panel ---
st.subheader("Service Status")
col1, col2, col3, col4 = st.columns(4)

with col1:
    openscope_ok = check_openscope()
    st.metric("OpenScope", "Running" if openscope_ok else "Offline",
              delta="OK" if openscope_ok else "Not Found",
              delta_color="normal" if openscope_ok else "inverse")

with col2:
    mcp_ok = check_mcp()
    st.metric("MCP Server", "Running" if mcp_ok else "Offline",
              delta="OK" if mcp_ok else "Not Found",
              delta_color="normal" if mcp_ok else "inverse")

with col3:
    llm_ok = check_llm()
    st.metric("LLM Server", "Running" if llm_ok else "Offline",
              delta="OK" if llm_ok else "Not Found",
              delta_color="normal" if llm_ok else "inverse")

with col4:
    vjepa_ok = check_vjepa()
    st.metric("V-JEPA", "Running" if vjepa_ok else "Offline",
              delta="OK" if vjepa_ok else "Not Found",
              delta_color="normal" if vjepa_ok else "inverse")

# --- Agent Controls ---
st.subheader("Agent Control")
col_timewarp, col_start, col_stop, col_status = st.columns([2, 1, 1, 2])

with col_timewarp:
    timewarp = st.slider("Timewarp", min_value=1, max_value=50, value=10,
                         disabled=st.session_state.agent_proc is not None,
                         help="Game speed multiplier (set before starting agent)")

with col_start:
    if st.button("Start Agent", disabled=st.session_state.agent_proc is not None):
        if not openscope_ok:
            st.error("Cannot start: OpenScope is not running at localhost:3003")
        else:
            try:
                # Start MCP server first if not running
                if not check_mcp():
                    st.session_state.mcp_proc = start_mcp()
                    time.sleep(1)  # Allow MCP to fully initialize

                # Start agent connected to MCP HTTP server
                proc, session_id = start_agent(timewarp=timewarp)
                st.session_state.agent_proc = proc
                st.session_state.session_id = session_id
                st.success(f"Agent started: {session_id}")
                st.rerun()
            except Exception as e:
                # Clean up MCP if agent failed to start
                if st.session_state.mcp_proc:
                    stop_mcp(st.session_state.mcp_proc)
                    st.session_state.mcp_proc = None
                st.error(f"Failed to start: {e}")

with col_stop:
    if st.button("Stop Agent", disabled=st.session_state.agent_proc is None):
        stop_agent(st.session_state.agent_proc)
        st.session_state.agent_proc = None
        # Stop MCP server if we started it
        if st.session_state.mcp_proc:
            stop_mcp(st.session_state.mcp_proc)
            st.session_state.mcp_proc = None
        st.info("Agent stopped")
        st.rerun()

with col_status:
    if st.session_state.agent_proc:
        poll = st.session_state.agent_proc.poll()
        if poll is None:
            st.info(f"Agent running: {st.session_state.session_id}")
        else:
            st.warning(f"Agent exited with code {poll}")
            st.session_state.agent_proc = None
            # CRITICAL: Also stop MCP when agent exits, otherwise next run fails
            # because MCP keeps the stale browser session
            if st.session_state.mcp_proc:
                stop_mcp(st.session_state.mcp_proc)
                st.session_state.mcp_proc = None
            st.rerun()  # Update UI to show agent stopped

# --- Main Content: OpenScope + Decisions ---
st.divider()
left_col, right_col = st.columns(2)

with left_col:
    st.subheader("OpenScope Radar")
    mcp_ok = check_mcp()
    if st.session_state.agent_proc and st.session_state.agent_proc.poll() is None:
        # Agent running - show live screenshots from MCP
        screenshot = fetch_screenshot()
        if screenshot:
            st.image(screenshot, use_container_width=True)
        else:
            st.warning("Waiting for screenshot from MCP server...")
    elif mcp_ok:
        # MCP running but no agent - still show screenshot
        screenshot = fetch_screenshot()
        if screenshot:
            st.image(screenshot, use_container_width=True)
        else:
            st.info("MCP connected but no active browser session")
    elif openscope_ok:
        # OpenScope running but agent not started - show placeholder
        st.info("Click **Start Agent** to begin")
        st.caption("The agent will control OpenScope in headless mode")
    else:
        st.error("OpenScope not running at localhost:3003")
        st.info("Start OpenScope: `cd openscope && npm start`")

with right_col:
    # --- Metrics at top (fixed position) ---
    st.subheader("Metrics")
    if st.session_state.session_id:
        events = read_events(st.session_state.session_id)
        metrics = get_metrics(events)
    else:
        events = []
        metrics = {"landings": 0, "success_rate": 0, "conflicts": 0, "score": 0}

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Landings", metrics["landings"])
    m2.metric("Success Rate", f"{metrics['success_rate']:.0f}%")
    m3.metric("Conflicts", metrics["conflicts"])
    m4.metric("Score", metrics["score"])

    # --- Decisions as terminal log ---
    st.subheader("Agent Decisions")

    if st.session_state.session_id:
        decisions = get_decisions(events)

        if decisions:
            # Build compact terminal-style log
            lines = []
            for d in reversed(decisions[-25:]):  # Show more in compact format
                if d["success"] is True:
                    lines.append(f"✓ {d['callsign']:8} {d['command']}")
                elif d["success"] is False:
                    err = d['error'][:20] if d['error'] else "rejected"
                    lines.append(f"✗ {d['callsign']:8} {d['command']} ({err})")
                else:
                    lines.append(f"⋯ {d['callsign']:8} {d['command']}")
            st.code("\n".join(lines), language=None)
        else:
            st.text("Waiting for decisions...")
    else:
        st.text("Start the agent to see decisions")

# --- Auto-refresh while agent is running ---
if st.session_state.agent_proc and st.session_state.agent_proc.poll() is None:
    time.sleep(2)
    st.rerun()
