# OrbitFlow Studio

OrbitFlow Studio is a local-first AI Agent Orchestration Platform: users create agents, wire them into visual workflows with conditions/loops, run tasks end-to-end, monitor execution live, and expose one agent through Telegram.

It is designed as an MVP that can be demoed like a mini n8n/LangGraph Studio.

## Why This Is Demo-Ready

- Agent CRUD with full config: `name`, `role`, `system_prompt`, `model`, `tools`, `channels`, `memory`, `guardrails`
- Visual workflow builder (React Flow) with conditional edges and loop-back routes
- 2 prebuilt templates:
  - `Support Routing Loop`
  - `Meeting Notes Loop`
- Telegram integration via `python-telegram-bot` in polling mode (no webhook/public URL needed)
- Live monitoring:
  - WebSocket event stream
  - execution logs
  - inter-agent message trail
  - token and estimated cost telemetry
  - color-coded runtime logs in backend terminal
- Threaded run history:
  - create/select workflow threads (Chat-style sessions)
  - clear history per thread or globally
- Seeded demo workflow and 3 seeded agents (2+ agents executing a real task)
- Local single-command bootstrap + run

## Architecture

```text
+------------------------------- OrbitFlow Studio ------------------------------+
|                                                                               |
|  React + Vite + React Flow UI                                                 |
|  - Agent Forge (CRUD)                                                         |
|  - Workflow Canvas (nodes, edges, conditions, loops)                          |
|  - Session Panel (run + live feed + metrics)                                  |
|                 |                                                             |
|                 | REST + WebSocket                                            |
|                 v                                                             |
|  FastAPI Backend                                                              |
|  - API Routes (agents/workflows/executions/monitoring)                        |
|  - OrchestratorService                                                        |
|  - LogBus (WebSocket broadcast)                                               |
|  - TelegramBridge (polling)                                                   |
|                 |                                                             |
|                 v                                                             |
|  LangGraph Runtime (StateGraph)                                               |
|  - Node = Agent invocation                                                    |
|  - Conditional routing                                                        |
|  - Feedback loop support                                                      |
|                 |                                                             |
|                 v                                                             |
|  Azure Inference Models (GitHub-backed)                                       |
|  - OpenAI-compatible chat completions                                          |
|  - OPENAI_API_KEY (or GITHUB_TOKEN) authentication                            |
|                                                                               |
|  Persistence: SQLite + SQLAlchemy                                             |
|  - agents, workflows, executions, logs, inter-agent messages                  |
+-------------------------------------------------------------------------------+
```

## Tech Stack

- Backend: FastAPI
- Runtime: LangGraph (`StateGraph`)
- LLM: Azure Inference endpoint (`https://models.inference.ai.azure.com`) with OpenAI-compatible client
- Messaging: Telegram (`python-telegram-bot`, polling mode)
- DB: SQLite + SQLAlchemy
- Frontend: React + Vite + React Flow
- Realtime: FastAPI WebSocket

## Azure Inference Model Syntax

This project uses the OpenAI-compatible interface against Azure Inference endpoint:

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],  # or GITHUB_TOKEN
    base_url="https://models.inference.ai.azure.com",
)
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
    ],
)
```

Implementation location: `backend/app/llm/github_models.py`.

## Project Structure

```text
backend/
  app/
    api/routes/            # FastAPI endpoints
    llm/github_models.py   # GitHub Models client adapter
    runtime/graph_engine.py# LangGraph execution engine
    services/              # orchestration + telegram bridge
    models.py              # SQLAlchemy models
    schemas.py             # API/domain schemas
    templates.py           # prebuilt workflows
frontend/
  src/
    components/            # Agent panel, canvas, run monitor
run_local.py               # one-command setup + start
```

## Single Setup Command (Local)

1. Configure env:
   - copy `backend/.env.example` to `backend/.env`
   - set `OPENAI_API_KEY` (or `GITHUB_TOKEN`)
   - optionally set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_AGENT_ID`
2. Run:

```bash
python run_local.py
```

This command automatically:
- creates `.venv` in the project root (if missing)
- installs backend dependencies into `.venv`
- installs frontend dependencies (if needed)
- starts backend/frontend services

Runtime URLs:
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`

## Manual Setup
1. Backend:
```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```
2. Frontend (new terminal):
```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## End-to-End Demo Flow (Support Example)

1. Open `http://localhost:5173`.
2. Use seeded workflow `OrbitFlow Support Loop`.
3. Submit prompt in Session panel:
   - `Customer cannot log in after password reset. Ask for safe recovery steps and next actions.`
4. Observe:
   - node-by-node runtime events
   - route decisions across conditional edges
   - final strategy output
   - token/cost metrics
   - inter-agent message records
5. Send a Telegram message to your bot and verify it responds via the configured Telegram-capable agent.

## Verification Playbook

### 1) Verify Feedback Loop Execution

Goal: prove `reviewer -> router` loop works when reviewer output contains `revise`.

1. Open workflow `OrbitFlow Support Loop`.
2. Ensure edge conditions are:
   - `router -> responder = always`
   - `responder -> reviewer = always`
   - `reviewer -> router = contains:revise`
3. Temporarily update reviewer system prompt to force one revision:
   - Example: `Always include the word revise in your first response, then continue normally.`
4. Run a thread with any support query.
5. Confirm in **Live Feed**:
   - one `edge_selected` event showing `reviewer -> router`
   - then another node cycle after reviewer (loop happened)
6. Reset reviewer prompt back to normal after test.

### 2) Verify Guardrail (`max_steps`)

Goal: prove loop protection stops runaway cycles.

1. Set workflow `Max steps` to a low number (for example `3`) and click `Save`.
2. Use loop-friendly conditions/prompt so revision is likely.
3. Run workflow and check **Live Feed** for `guardrail_stop`.
4. Confirm execution status ends as completed/terminated, not infinite.

### 3) Verify Memory / Context Behavior

Current MVP behavior:
- Agent `memory` is persisted and injected into node prompt.
- Recent thread history (last few user/assistant turns) is appended to subsequent runs in the same thread.

How to test thread context:
1. In `Thread 1`, run query A: `User forgot password and 2FA device changed.`
2. In same thread, run query B: `Give me the follow-up plan based on previous advice.`
3. Validate B output references prior context from query A.

How to test agent memory injection:
1. Update an agent via API with memory payload (example):
```bash
curl -X PUT http://localhost:8000/api/agents/<agent_id> \
  -H "Content-Type: application/json" \
  -d "{\"memory\":{\"tone\":\"formal\",\"region\":\"US\"}}"
```
2. Run workflow and verify generated output reflects that profile tendency.

## Telegram Demo Checklist

1. Set `TELEGRAM_BOT_TOKEN` in `backend/.env`.
2. Optionally set `TELEGRAM_AGENT_ID` to force a specific agent, or ensure one agent has `telegram` in `channels`.
3. Restart backend.
4. Check backend terminal log:
   - `telegram bridge starting in polling mode.` (success)
   - `telegram disabled ...` (token missing)
5. In Telegram chat with your bot:
   - send `/start` and verify welcome message.
   - send a normal message and verify agent-generated response.
6. Confirm runtime telemetry:
   - terminal/log bus includes `telegram_message` events.

## Implemented vs Planned (MVP)

- Implemented:
  - Agent CRUD
  - Conditional workflow edges + feedback loops
  - Max-step guardrail
  - Agent output guardrails (`max_output_chars`, `blocked_terms`)
  - Threaded history and monitoring
  - Inter-agent handoff persistence
- Partial:
  - Memory/context management (agent memory profile + recent thread context)
- Planned:
  - Scheduled workflow triggers
  - Skill/plugin execution framework

## API Surface (MVP)

- `GET/POST/PUT/DELETE /api/agents`
- `GET/POST/PUT/DELETE /api/workflows`
- `GET /api/workflows/templates/library`
- `POST /api/workflows/templates/create`
- `POST /api/executions` (async start)
- `GET /api/executions/{id}`
- `GET/POST/PUT/DELETE /api/threads`
- `GET /api/monitoring/executions/{id}/logs`
- `GET /api/monitoring/executions/{id}/messages`
- `GET /api/monitoring/summary`
- `DELETE /api/monitoring/history` (supports `thread_id` and `workflow_id`)
- `WS /api/monitoring/ws/live`

## Tests

Critical path tests are included in `backend/tests/test_core_paths.py`:

- Agent CRUD
- Workflow execution completion
- Inter-agent message delivery persistence

Run tests:

```bash
cd backend
pytest
```

## How To Add New Workflow Templates

1. Add template definition in `backend/app/templates.py`.
2. Include:
   - `id`, `name`, `description`
   - template `nodes` with `role_hint`
   - `edges` with conditions (`always`, `contains:*`, `regex:*`, etc.)
3. In UI, users can instantiate templates using role-based agent mapping.

## How To Add New Messaging Channels

1. Add a channel bridge service under `backend/app/services/`.
2. Inject bridge startup/shutdown in `backend/app/main.py` lifespan.
3. Reuse `OrchestratorService` for message-to-agent execution.
4. Tag compatible agents by adding channel names in `channels`.

## Runtime Choice Justification

- LangGraph over CrewAI/AutoGen:
  - explicit graph model with conditional edges and loop control
  - directly mirrors the visual builder mental model
  - auditable control flow
- FastAPI over Flask:
  - async-native for WebSocket + background execution
- Telegram polling over webhook:
  - works fully local, no public URL or infra dependency
- SQLite:
  - zero-config local persistence; easy swap to Postgres later
- Azure Inference Models:
  - no direct paid OpenAI subscription required
  - model string swap keeps provider portability
