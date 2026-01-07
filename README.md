# AI ATC Demo

A Streamlit interface for live demonstrations of the AI ATC agent system.

## Quick Start

```bash
# 1. Start OpenScope (required)
cd ../openscope && npm start

# 2. Start LLM server (optional - for critic mode)
# Use LMStudio, vLLM, or Ollama at localhost:1234

# 3. Start V-JEPA server (optional - for visual analysis)
# cd ../vjepa-server && ./scripts/start_cluster.sh

# 4. Run the demo
cd ai-atc-demo
uv run streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Features

- **Service Status Panel**: Shows health of OpenScope, LLM, and V-JEPA
- **Live Radar View**: OpenScope embedded in an iframe (real-time)
- **Agent Control**: Start/stop the agent with one click
- **Decision Stream**: Live feed of agent commands and outcomes
- **Metrics Dashboard**: Landings, success rate, conflicts, score

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         app.py (Streamlit)                       │
│     [health checks]  [agent subprocess]  [JSONL reading]        │
└─────────────────────────────────────────────────────────────────┘
              │                      │
              ▼                      ▼
        HTTP checks          openscope-llm-agent (subprocess)
              │                      │ (manages MCP via stdio)
              ▼                      ▼
   OpenScope:3003    LLM:1234    V-JEPA:8001
```

## Requirements

- Python 3.10+
- uv package manager
- OpenScope running at localhost:3003
- openscope-llm-agent in sibling directory

## Troubleshooting

**OpenScope iframe not loading?**
- Check that OpenScope is running: `curl localhost:3003`
- Some browsers block iframes - try a different browser

**Agent not starting?**
- Ensure openscope-llm-agent exists at `../openscope-llm-agent`
- Check logs in `./logs/{session_id}/`

**Decisions not updating?**
- Click the "Refresh" button to reload events
- Check that the agent process is still running
