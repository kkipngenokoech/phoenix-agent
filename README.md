# Phoenix Agent

An autonomous multi-agent system for intelligent code refactoring. Phoenix Agent analyzes codebases, identifies code smells, generates refactoring plans, applies changes in parallel, and verifies correctness — all through a closed-loop control system with persistent memory.

**[Live Demo](https://phoenix-agent.vercel.app)** · **[Documentation](https://kipngenokoech.com/projects/phoenix-agent/)** · **[Backend API](https://monkfish-app-eo2ul.ondigitalocean.app/health)**

---

## Table of Contents

- [Key Features](#key-features)
- [Architecture](#architecture)
- [Multi-Agent Crew System](#multi-agent-crew-system)
- [7-Phase Control Loop](#7-phase-control-loop)
- [Persistent State Management](#persistent-state-management)
- [Evaluation Framework](#evaluation-framework)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Usage](#usage)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [API Reference](#api-reference)

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Multi-Agent Architecture** | Lead agent orchestrates specialized sub-agents (Analyzer, Strategist, Coder, Tester) with parallel execution |
| **7-Phase Control Loop** | OBSERVE → REASON → PLAN → DECIDE → ACT → VERIFY → UPDATE with adaptive retry |
| **3-Layer Memory** | Redis (session state) + PostgreSQL (refactoring history) + Neo4j (knowledge graph) |
| **Parallel Code Generation** | Multiple CoderAgents modify files concurrently via ThreadPoolExecutor |
| **Human-in-the-Loop** | Approval gate before code changes; review gate after verification |
| **Real-Time Streaming** | WebSocket event stream powers a live phase stepper, terminal log, and diff viewer |
| **GitHub-Style File Browser** | Original vs. refactored file comparison with syntax highlighting |
| **Evaluation Metrics** | Cyclomatic complexity, maintainability index, code smell count, test pass rate, lines of code |
| **Adaptive Control** | Closed-loop — verification failures trigger re-planning with error context |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Next.js Frontend                     │
│  RefactorForm → PhaseStepper → DiffReview → FileViewer  │
└────────────────────────┬────────────────────────────────┘
                         │ WebSocket + REST
┌────────────────────────▼────────────────────────────────┐
│                   FastAPI Backend                         │
│  ┌──────────┐  ┌───────────┐  ┌───────────────────────┐ │
│  │  Routes   │  │ WebSocket │  │   Agent Registry      │ │
│  └──────────┘  └───────────┘  └───────────────────────┘ │
│                         │                                │
│  ┌──────────────────────▼───────────────────────────┐   │
│  │              Lead Agent (Orchestrator)             │   │
│  │  ┌──────────┐ ┌────────────┐ ┌────────────────┐  │   │
│  │  │ Analyzer │ │ Strategist │ │ Coder (×N)     │  │   │
│  │  │ OBS+RSN  │ │ PLAN+DEC   │ │ parallel ACT   │  │   │
│  │  └──────────┘ └────────────┘ └────────────────┘  │   │
│  │                               ┌────────────────┐  │   │
│  │                               │    Tester       │  │   │
│  │                               │    VERIFY       │  │   │
│  │                               └────────────────┘  │   │
│  └──────────────────────────────────────────────────┘   │
│                         │                                │
│  ┌──────────────────────▼───────────────────────────┐   │
│  │               Memory Layer                        │   │
│  │  Redis (session) │ PostgreSQL (history) │ Neo4j   │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Multi-Agent Crew System

Phoenix uses a **crew-style multi-agent architecture** where a [Lead Agent](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/crew/lead_agent.py) orchestrates four specialized sub-agents:

| Agent | Role | Source |
|-------|------|--------|
| **[AnalyzerAgent](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/crew/analyzer_agent.py)** | Runs OBSERVE + REASON phases — parses the codebase with AST tools, identifies code smells, computes complexity metrics | [`crew/analyzer_agent.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/crew/analyzer_agent.py) |
| **[StrategistAgent](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/crew/strategist_agent.py)** | Runs PLAN + DECIDE phases — generates a step-by-step refactoring plan, evaluates risk, and decides execution order | [`crew/strategist_agent.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/crew/strategist_agent.py) |
| **[CoderAgent](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/crew/coder_agent.py)** | Runs ACT phase — each instance gets its own LLM and modifies a single file. Multiple CoderAgents run **in parallel** via `ThreadPoolExecutor` | [`crew/coder_agent.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/crew/coder_agent.py) |
| **[TesterAgent](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/crew/tester_agent.py)** | Runs VERIFY phase — executes the test suite, compares before/after metrics, produces a verification report | [`crew/tester_agent.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/crew/tester_agent.py) |

The base abstraction is defined in [`crew/base_agent.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/crew/base_agent.py), and task/result types in [`crew/task.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/crew/task.py).

### Parallel Execution

The Lead Agent submits independent `modify_code` steps to a `ThreadPoolExecutor`. Each CoderAgent gets its own LLM instance (thread-safe), and each writes to a different file — eliminating write conflicts:

```python
# From lead_agent.py — parallel coding
with ThreadPoolExecutor(max_workers=config.max_coder_agents) as pool:
    futures = {
        pool.submit(coder.execute, task): task
        for task in coding_tasks
    }
    for future in as_completed(futures):
        result = future.result()  # TaskResult
```

---

## 7-Phase Control Loop

Each refactoring iteration follows a strict seven-phase loop, implemented across the [orchestrator modules](https://github.com/kkipngenokoech/phoenix-agent/tree/main/src/phoenix_agent/orchestrator):

| Phase | Module | Description |
|-------|--------|-------------|
| **OBSERVE** | [`observer.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/orchestrator/observer.py) | AST parsing, code smell detection, complexity metrics, test execution |
| **REASON** | [`reasoner.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/orchestrator/reasoner.py) | LLM analyzes observations, identifies root causes, prioritizes issues |
| **PLAN** | [`planner.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/orchestrator/planner.py) | Generates ordered refactoring steps with file paths and descriptions |
| **DECIDE** | [`arbiter.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/orchestrator/arbiter.py) | Risk assessment, confidence scoring, go/no-go decision |
| **ACT** | [`executor.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/orchestrator/executor.py) | LLM generates code, writes modified files (parallelized in crew mode) |
| **VERIFY** | [`verifier.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/orchestrator/verifier.py) | Re-runs tests, re-computes metrics, compares before/after |
| **UPDATE** | [`updater.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/orchestrator/updater.py) | Persists results to PostgreSQL, updates session state, optionally commits via git |

### Adaptive Control (Closed-Loop)

If verification **fails** (tests break or metrics regress), the agent:
1. Reverts changes to the last known-good state
2. Feeds the failure report back as context for the next iteration
3. Re-plans with awareness of what went wrong
4. Retries up to `max_iterations` (default: 3)

This closed-loop ensures the agent converges on correct refactorings rather than blindly applying changes.

---

## Persistent State Management

Phoenix uses a **3-layer memory architecture** to maintain state across phases, sessions, and projects:

| Layer | Technology | Purpose | Source |
|-------|-----------|---------|--------|
| **Session Memory** | Redis (24hr TTL) | Current session state, phase data, WebSocket event queues | [`memory/session.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/memory/session.py) |
| **History Store** | PostgreSQL | Complete refactoring records — plans, metrics, original/refactored file contents, durations | [`memory/history.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/memory/history.py) |
| **Knowledge Graph** | Neo4j | Codebase relationships — functions, classes, dependencies, call graphs | [`memory/knowledge_graph.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/memory/knowledge_graph.py) |

### Schema (PostgreSQL)

The `refactoring_history` table stores:
- Session metadata (ID, timestamp, duration, status)
- The full refactoring plan (JSONB)
- Before/after metrics (JSONB) — complexity, maintainability, smell count
- Original file contents and refactored file contents (JSONB)
- Verification reports

---

## Evaluation Framework

Phoenix computes **5 quantitative metrics** before and after each refactoring:

| Metric | Description | Tool |
|--------|-------------|------|
| **Cyclomatic Complexity** | Number of independent code paths | [`ast_parser.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/tools/ast_parser.py) |
| **Maintainability Index** | Composite score (0–100) based on Halstead volume, cyclomatic complexity, and LOC | [`ast_parser.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/tools/ast_parser.py) |
| **Code Smell Count** | Number of detected smells (long methods, god classes, deep nesting, etc.) | [`ast_parser.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/tools/ast_parser.py) |
| **Test Pass Rate** | Percentage of passing tests after changes | [`test_runner.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/tools/test_runner.py) |
| **Lines of Code** | Total LOC (measures if refactoring reduces bloat) | [`ast_parser.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/tools/ast_parser.py) |

### Sample Project (Test Suite)

The [`sample_project/`](https://github.com/kkipngenokoech/phoenix-agent/tree/main/sample_project) contains intentional code smells across 5+ files with **39 passing tests**. It serves as the evaluation target:

```bash
cd sample_project && pytest tests/ -v
# 39 passed
```

The agent must maintain a 100% test pass rate while improving other metrics.

---

## Project Structure

```
phoenix-agent/
├── src/phoenix_agent/
│   ├── agent.py                    # Main PhoenixAgent entry point
│   ├── models.py                   # Pydantic models (RefactoringPlan, etc.)
│   ├── config.py                   # AgentConfig with all settings
│   ├── provider.py                 # LLM provider factory (Anthropic/OpenAI/Groq/Ollama)
│   ├── crew/                       # Multi-agent crew system
│   │   ├── lead_agent.py           # Orchestrator — delegates to sub-agents
│   │   ├── analyzer_agent.py       # OBSERVE + REASON
│   │   ├── strategist_agent.py     # PLAN + DECIDE
│   │   ├── coder_agent.py          # ACT (parallel file modifications)
│   │   ├── tester_agent.py         # VERIFY
│   │   ├── base_agent.py           # SubAgent ABC
│   │   ├── task.py                 # Task/TaskResult dataclasses
│   │   └── code_gen.py             # Shared code generation utilities
│   ├── orchestrator/               # Phase implementations
│   │   ├── observer.py             # AST analysis + metrics
│   │   ├── reasoner.py             # LLM-based reasoning
│   │   ├── planner.py              # Refactoring plan generation
│   │   ├── arbiter.py              # Risk assessment + decision
│   │   ├── executor.py             # Code generation + file writing
│   │   ├── verifier.py             # Test execution + metric comparison
│   │   └── updater.py              # Persistence + finalization
│   ├── memory/                     # 3-layer state management
│   │   ├── session.py              # Redis session store
│   │   ├── history.py              # PostgreSQL history store
│   │   └── knowledge_graph.py      # Neo4j knowledge graph
│   ├── tools/                      # Agent tools
│   │   ├── ast_parser.py           # AST parsing + code smell detection
│   │   ├── test_runner.py          # pytest execution
│   │   ├── git_ops.py              # Git operations (commit, diff, revert)
│   │   └── test_generator.py       # LLM-based test generation
│   ├── api/                        # FastAPI backend
│   │   ├── main.py                 # App factory + CORS
│   │   ├── routes.py               # REST endpoints
│   │   ├── websocket.py            # WebSocket event streaming
│   │   ├── agent_registry.py       # Session → agent mapping
│   │   └── schemas.py              # Request/response schemas
│   └── cli.py                      # CLI entry point
├── frontend/                       # Next.js 14 frontend
│   └── src/
│       ├── app/
│       │   ├── page.tsx             # Landing page with RefactorForm
│       │   ├── session/[id]/page.tsx # Live session view
│       │   └── history/page.tsx     # Refactoring history
│       ├── components/
│       │   ├── PhaseStepper.tsx      # 7-phase progress indicator
│       │   ├── DiffReview.tsx        # Code diff viewer
│       │   ├── MetricsCard.tsx       # Before/after metrics
│       │   ├── TerminalLog.tsx       # Real-time event log
│       │   └── RefactorForm.tsx      # Project path + request input
│       ├── hooks/
│       │   └── useAgentSocket.ts     # WebSocket hook
│       └── lib/
│           └── api.ts               # API client
├── sample_project/                  # Evaluation target (39 tests)
├── docker-compose.yml               # Dev infrastructure (Redis + PG + Neo4j)
├── docker-compose.prod.yml          # Production stack
├── Dockerfile                       # Backend container
└── frontend/Dockerfile              # Frontend container
```

---

## Installation

### Prerequisites

- Python 3.10+
- Node.js 18+ (for frontend)
- Docker & Docker Compose (for infrastructure)

### 1. Clone and Install

```bash
git clone https://github.com/kkipngenokoech/phoenix-agent.git
cd phoenix-agent

# Python dependencies
pip install -e .

# Frontend dependencies
cd frontend && npm install && cd ..
```

### 2. Start Infrastructure

```bash
docker-compose up -d  # Redis + PostgreSQL + Neo4j
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your LLM provider credentials
```

### 4. Run Database Migrations

```bash
# Apply schema
docker exec -i phoenix-agent-postgres-1 psql -U phoenix -d phoenix < migrations/001_init.sql
docker exec -i phoenix-agent-postgres-1 psql -U phoenix -d phoenix < migrations/002_add_file_contents.sql
```

---

## Usage

### Web Interface (Recommended)

Start the backend and frontend:

```bash
# Terminal 1: Backend
PYTHONPATH=src uvicorn phoenix_agent.api.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```

Open [http://localhost:3000](http://localhost:3000):
1. Enter the project path and refactoring request
2. Watch the 7-phase loop execute in real-time via the phase stepper
3. Approve or reject the plan at the human-in-the-loop gate
4. Review diffs and before/after metrics
5. Browse original vs. refactored files in the GitHub-style file viewer

### CLI

```bash
PYTHONPATH=src python -m phoenix_agent refactor sample_project/ "Extract long methods and reduce complexity"
```

### Programmatic

```python
from phoenix_agent.agent import PhoenixAgent
from phoenix_agent.config import AgentConfig

config = AgentConfig()
agent = PhoenixAgent(config)

result = await agent.run(
    target_path="sample_project/",
    request="Refactor the calculate_statistics function to reduce cyclomatic complexity"
)
```

---

## Deployment

### Production (DigitalOcean + Vercel)

The live deployment uses:
- **Backend**: DigitalOcean App Platform — [`Dockerfile`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/Dockerfile) + [`.do/app.yaml`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/.do/app.yaml)
- **Frontend**: Vercel — [`frontend/Dockerfile`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/frontend/Dockerfile)
- **Database**: DigitalOcean managed PostgreSQL

### Self-Hosted (Docker Compose)

```bash
docker-compose -f docker-compose.prod.yml up -d
```

See the [Deployment Guide](https://kipngenokoech.com/projects/phoenix-agent/) for full instructions.

---

## Configuration

All settings are managed via [`config.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/config.py) and environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | `anthropic`, `openai`, `groq`, `ollama`, `google` | `anthropic` |
| `LLM_MODEL` | Model identifier | `claude-sonnet-4-20250514` |
| `LLM_API_KEY` | API key for the chosen provider | — |
| `LLM_BASE_URL` | Custom API endpoint (for gateways) | — |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://phoenix:phoenix@localhost:5432/phoenix` |
| `NEO4J_URI` | Neo4j bolt URI | `bolt://localhost:7687` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `SKIP_GIT_OPERATIONS` | Disable git commits (for hosted envs) | `false` |
| `CORS_ORIGIN` | Allowed frontend origin (production) | — |

---

## API Reference

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/refactor` | Start a new refactoring session |
| `GET` | `/api/sessions/{id}` | Get session details (metrics, files, status) |
| `GET` | `/api/history` | List all past refactoring sessions |
| `POST` | `/api/sessions/{id}/approve` | Approve the refactoring plan |
| `POST` | `/api/sessions/{id}/reject` | Reject the plan |
| `GET` | `/health` | Health check |

### WebSocket

Connect to `ws://localhost:8000/ws/{session_id}` to receive real-time events:

```json
{"type": "phase", "data": {"phase": "OBSERVE", "status": "running"}}
{"type": "observation", "data": {"metrics": {...}, "smells": [...]}}
{"type": "plan", "data": {"steps": [...]}}
{"type": "act_step", "data": {"step": 1, "file": "src/utils.py", "status": "done"}}
{"type": "completed", "data": {"metrics_before": {...}, "metrics_after": {...}}}
```

Full API documentation: [REST API](https://kipngenokoech.com/projects/phoenix-agent/) · [WebSocket API](https://kipngenokoech.com/projects/phoenix-agent/)

---

## Tools

All tools extend [`BaseTool`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/tools/base.py) and are managed by the [tool registry](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/tools/registry.py):

| Tool | Source | Purpose |
|------|--------|---------|
| **AST Parser** | [`ast_parser.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/tools/ast_parser.py) | Parse Python AST, detect code smells, compute complexity metrics |
| **Test Runner** | [`test_runner.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/tools/test_runner.py) | Execute pytest, capture results, compute pass rate |
| **Git Ops** | [`git_ops.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/tools/git_ops.py) | Commit changes, generate diffs, revert on failure |
| **Test Generator** | [`test_generator.py`](https://github.com/kkipngenokoech/phoenix-agent/blob/main/src/phoenix_agent/tools/test_generator.py) | LLM-powered test case generation |

---

## License

MIT

## Acknowledgments

- Built for CMU 04-801-W3 Agentic AI Engineering
- LLM integration via [LiteLLM](https://github.com/BerriAI/litellm) (multi-provider support)
- Frontend built with [Next.js 14](https://nextjs.org/) + [shadcn/ui](https://ui.shadcn.com/)
- Infrastructure: Redis, PostgreSQL, Neo4j
