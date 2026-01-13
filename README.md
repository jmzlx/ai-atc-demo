# AI ATC Demo

SvelteKit + FastAPI interface for live monitoring and session replay of the AI ATC agent system.

## Quick Start

```bash
# 1. Start OpenScope (required)
cd ../openscope && npm start

# 2. Start LLM server (required for agent)
# Use LMStudio, vLLM, or Ollama at localhost:1234

# 3. Start the backend
cd ai-atc-demo
uv run uvicorn backend.main:app --reload --port 8000

# 4. Start the frontend (in another terminal)
cd ai-atc-demo/frontend
npm run dev
```

Open http://localhost:5173 in your browser.

## Features

### Live Monitoring (`/live`)
- **Service Status**: Health of OpenScope, MCP, LLM, V-JEPA
- **Live Radar**: Screenshots from MCP server (2s polling)
- **Agent Control**: Start/stop agent with timewarp setting
- **Decision Stream**: Real-time feed of commands and outcomes
- **Metrics Dashboard**: Landings, success rate, conflicts, score

### Session Replay (`/replay/{id}`)
- **Timeline**: Scrubable timeline with event markers (conflicts, ILS clearances)
- **Playback Controls**: Play/pause, speed (0.5x-10x), seek
- **Aircraft State**: Interpolated positions between snapshots
- **Decision Log**: Commands synced to playback time
- **Keyboard Shortcuts**: Space (play/pause), ←→ (seek), +− (speed)

### Session Browser (`/sessions`)
- List all past sessions with metadata
- Filter by date, model, score

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     SvelteKit Frontend (:5173)                   │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────┐  │
│  │ Session List │  │  Live Monitor │  │   Session Replay     │  │
│  └──────────────┘  └───────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend (:8000)                      │
│  GET  /api/sessions              - List sessions                 │
│  GET  /api/sessions/{id}/events  - Events for replay             │
│  GET  /api/screenshot            - Proxy to MCP                  │
│  GET  /api/health                - Service health                │
│  POST /api/agent/start           - Start MCP + agent             │
│  POST /api/agent/stop            - Stop agent                    │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
          MCP:8080     Agent subprocess   JSONL logs
              │               │
              ▼               ▼
       OpenScope:3003    LLM:1234
```

## Requirements

- Python 3.10+
- Node.js 18+
- uv package manager
- OpenScope running at localhost:3003
- openscope-llm-agent in sibling directory
- mcp-openscope in sibling directory

## Development

```bash
# Backend
uv sync
uv run uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sessions` | GET | List all sessions |
| `/api/sessions/{id}` | GET | Session metadata |
| `/api/sessions/{id}/events` | GET | All events for replay |
| `/api/health` | GET | Service health checks |
| `/api/screenshot` | GET | Proxy screenshot from MCP |
| `/api/agent/start` | POST | Start MCP + agent |
| `/api/agent/stop` | POST | Stop agent |
| `/api/agent/status` | GET | Agent running status |
