# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

毕业论文 Word 排版 Agent — an automated thesis formatting tool that parses university formatting rules, checks thesis `.docx` files against those rules, and generates fixed documents. Monorepo with a Python/FastAPI backend and a React/TypeScript frontend.

## Commands

### Docker (recommended)
```bash
docker-compose up -d                    # Start all services (Postgres, Redis, MinIO, API, Worker, Web)
docker-compose exec api alembic upgrade head  # Initialize/migrate database
docker-compose logs -f api              # Watch API logs
docker-compose down -v                  # Full reset (destroys data volumes)
```

### Backend (thesis-formatter-api)
```bash
cd thesis-formatter-api
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head                              # Run migrations
uvicorn app.main:app --reload                     # Dev server on :8000
celery -A app.tasks.celery_app worker --loglevel=info  # Celery worker
pytest                                            # Run all tests
pytest tests/test_checker.py                      # Run single test file
pytest -k "test_name"                             # Run single test by name
```

### Frontend (thesis-formatter-web)
```bash
cd thesis-formatter-web
npm install
npm run dev       # Dev server on :5173 (proxies /api to localhost:8000)
npm run test      # Run tests
npm run build     # Production build
```

## Architecture

### Request Flow

User uploads `.docx` via frontend -> `POST /api/v1/tasks` stores file in MinIO, creates `Task` row, dispatches Celery task -> Celery worker downloads file, runs `DocumentProcessor` pipeline (parse -> check -> fix -> generate), writes results to DB -> Frontend polls `GET /tasks/{id}` every 3s until completion.

### Backend Structure (thesis-formatter-api/app/)

- **api/v1/endpoints/** — Four route groups: `tasks`, `rules`, `models`, `templates`
- **models/models.py** — Six SQLAlchemy 2.0+ models with UUID PKs and JSONB fields: `Task`, `Issue`, `Change`, `Rule`, `Template`, `ModelConfig`
- **services/docx/** — Four-stage document processing pipeline:
  - `parser.py` (DocxParser) — extracts structure from `.docx` using python-docx, including east-asia font info via XML
  - `checker.py` (FormatChecker) — 10 check methods across 8 formatting dimensions, returns `Issue` dataclasses
  - `fixer.py` (FormatFixer) — modifies only formatting attributes, never text content; records `ChangeRecord` with risk levels
  - `generator.py` (DocxGenerator) — produces markdown changelog and report
  - `processor.py` (DocumentProcessor) — orchestrator chaining the above
- **services/ai/** — `LLMProvider` ABC with `OpenAICompatibleProvider` implementation; `ModelManager` for multi-provider priority fallback; `SpecParser` for AI-powered rule extraction from spec documents
- **services/rule/engine.py** — `RuleEngine` with rule priority chain: task.rule_snapshot > template.rule > built-in defaults (Chinese university thesis standards)
- **services/storage.py** — MinIO wrapper with presigned URL downloads
- **tasks/format_tasks.py** — Three Celery tasks using `asyncio.run()` to bridge sync workers with async DB: `process_format_check`, `process_format_fix`, `parse_spec_file`
- **core/config.py** — pydantic-settings `BaseSettings` singleton; all config via env vars
- **core/security.py** — Fernet encryption for AI API keys

### Frontend Structure (thesis-formatter-web/src/)

- **pages/** — Five routes: `HomePage` (landing), `UploadPage` (file upload + config), `ResultPage` (polling + report table), `PreviewPage` (stub), `DownloadPage` (fixed doc + changelog)
- **services/** — Axios instance with `baseURL: '/api/v1'`; domain modules: `taskApi.ts`, `ruleApi.ts`, `modelApi.ts`
- **store/taskStore.ts** — Zustand store for task polling state (3s interval)
- **hooks/useTaskPolling.ts** — React hook wrapping store polling with lifecycle cleanup
- **types/index.ts** — All TypeScript interfaces in a single barrel file
- **components/AppHeader.tsx** — Ant Design layout header with navigation

### Key Design Decisions

- **Rule freezing**: Rules are snapshotted into `Task.rule_snapshot` at creation time so rule changes don't affect in-progress tasks.
- **Async-first backend**: FastAPI + async SQLAlchemy + asyncpg. Celery bridges to async via `asyncio.run()`.
- **AI abstraction**: Any OpenAI-compatible API works (DeepSeek, Qwen, Ollama, SiliconFlow). Provider auto-detected from base URL. API keys encrypted at rest with Fernet.
- **Document safety**: The fixer only modifies formatting attributes (margins, fonts, spacing, etc.), never text content.

### Services at Startup

The app depends on: PostgreSQL 16 (asyncpg), Redis 7 (Celery broker + result backend on separate DBs), MinIO (S3-compatible object storage). All configured via env vars with sensible localhost defaults in `.env.example`.

### Testing

Tests use SQLite in-memory (`sqlite+aiosqlite`) with dependency overrides for `get_db`. MinIO and Celery are mocked. Fixtures in `tests/conftest.py` build DOCX files programmatically with intentional formatting errors. pytest-asyncio mode is `"auto"`.
