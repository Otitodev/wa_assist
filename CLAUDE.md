# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Whaply** – A full-stack SaaS platform for WhatsApp automation with intelligent human/AI collision detection. The core value is **"Invisible Mute"**: the AI automatically pauses when a business owner takes over a chat, preventing message conflicts.

- **Backend**: FastAPI at `app/` – webhook ingestion, session state machine, LLM reply pipeline, multi-tenant persistence
- **Frontend**: Next.js 16 at `frontend/` – operational dashboard for monitoring sessions, instances, and knowledge base
- **Database**: Supabase/Postgres (schema at `database/schema.sql`)
- **Deployment target**: Railway (backend), Vercel (frontend); `Procfile` and `runtime.txt` present

## Architecture

### Message Flow
```
WhatsApp User → Evolution API → POST /webhook/{instance}
                                       ↓
                              Idempotency check (processed_events)
                                       ↓
                              Tenant lookup by instance_name
                              Message stored in messages table
                              Session upserted
                                       ↓
                         fromMe=true? → Pause session (collision detection)
                         fromMe=false + not paused? → LLM reply pipeline
                                       ↓
                              LLM generate (Anthropic/OpenAI)
                              Optional message delay (anti-ban)
                              Optional typing indicator
                              Evolution API send
```

**Alternative ingestion**: WebSocket mode (`WEBSOCKET_ENABLED=true`) connects directly to Evolution API instead of using webhooks.

### Auth Architecture (Two-Layer)
Authentication is split between Next.js and FastAPI:

1. **BetterAuth (Next.js)** – `frontend/src/lib/auth.ts` handles signup, login, password reset via `/api/auth/*` routes. Uses direct Postgres connection (`DATABASE_URL`). Email via Resend.
2. **FastAPI session validation** – `app/auth/dependencies.py` validates requests by looking up the BetterAuth session token in the `session` table (Supabase). No JWT crypto — it reads `session.token → session.userId → user + user_tenants`.
3. **Tenant RBAC** – `require_tenant_access(role)` dependency factory enforces `owner > admin > member` role hierarchy per tenant.

### Module Map

| File | Responsibility |
|---|---|
| `app/main.py` | FastAPI app, all routes, webhook handler, startup/shutdown |
| `app/config.py` | All env var loading — read this to know what's configurable |
| `app/db.py` | Supabase client singleton (service role key, bypasses RLS) |
| `app/evolve_parse.py` | Extracts `chat_id`, `message_id`, `fromMe`, `text` from Evolution payloads |
| `app/services/collision.py` | `should_pause_on_event()` – returns `True` for `messages.upsert` with `fromMe=true` |
| `app/services/evolution_client.py` | `EvolutionClient` – `send_text_message()`, `get_instance_status()` |
| `app/services/llm_client.py` | Factory: returns Anthropic or OpenAI provider based on `LLM_PROVIDER` |
| `app/services/llm_providers/` | `base.py` (abstract), `anthropic_provider.py`, `openai_provider.py` |
| `app/services/evolution_websocket.py` | WebSocket client for Evolution API (alternative to webhooks) |
| `app/services/websocket_handler.py` | Handles messages received via WebSocket connection |
| `app/logger.py` | Structured JSON logging with context fields (`tenant_id`, `chat_id`, etc.) |
| `app/auth/` | `routes.py` (`GET /api/auth/me`), `dependencies.py` (session validation), `service.py` |
| `scripts/auto_resume.py` | Standalone cron script — calls `/cron/auto-resume` |
| `database/schema.sql` | Full Postgres schema — run in Supabase SQL Editor to initialize |

### Database Schema (4 tables)

- **`tenants`** – `instance_name` (unique), `evo_server_url`, `evo_api_key`, `system_prompt`, `llm_provider`
- **`sessions`** – `(tenant_id, chat_id)` unique; `is_paused`, `pause_reason`, `last_message_at`, `last_human_at`
- **`messages`** – `(tenant_id, message_id)` unique; `from_me`, `message_type`, `text`, `raw` (JSONB)
- **`processed_events`** – `(tenant_id, message_id, event_type)` unique; idempotency tracking; action logged as `paused | ai_replied | ai_failed | ignored_paused`

BetterAuth creates its own tables (`user`, `session`, `account`) in the same Postgres database.

### Frontend Structure

```
frontend/src/
  app/
    (app)/          # Authenticated route group
      dashboard/
      instances/    # [name]/ sub-route for detail
      sessions/     # [id]/ sub-route for detail
      knowledge/
      settings/
    (auth)/         # Unauthenticated route group
      login/ register/ forgot-password/ reset-password/
    api/auth/       # BetterAuth Next.js API handler
  components/
    layout/         # Sidebar, topbar, shell
    shared/         # data-table.tsx, status-badge.tsx, timeline.tsx
    ui/             # shadcn/ui generated components
  lib/
    api.ts          # Centralized API client (fetch wrapper + Zod validation)
    auth.ts         # BetterAuth server config (Postgres pool + Resend)
    auth-client.ts  # BetterAuth React client
    utils.ts
  hooks/
  types/
```

## Development Commands

### Backend
```bash
# Setup
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env      # Fill in SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, LLM keys

# Run
uvicorn app.main:app --reload --port 8000

# Test
pytest
pytest tests/test_collision.py

# Lint/Format/Types
black app/
flake8 app/
mypy app/
```

### Frontend
```bash
cd frontend
npm install
# Set DATABASE_URL, BETTER_AUTH_SECRET, RESEND_API_KEY, NEXT_PUBLIC_APP_URL in .env.local

npm run dev    # localhost:3000
npm run build
npm run lint
```

### Add shadcn components
```bash
cd frontend
npx shadcn@latest add <component-name>
```

## Key Environment Variables

**Backend** (`.env`):
```
SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
EVOLUTION_WEBHOOK_SHARED_SECRET, CRON_SECRET
LLM_PROVIDER=anthropic|openai, ANTHROPIC_API_KEY, OPENAI_API_KEY
CORS_ORIGINS=http://localhost:3000,...
RESUME_AFTER_HOURS=2
WEBSOCKET_ENABLED=false, WEBSOCKET_MODE=global, EVOLUTION_SERVER_URL, EVOLUTION_API_KEY
MESSAGE_DELAY_ENABLED=true, MESSAGE_DELAY_MIN_MS=1000, MESSAGE_DELAY_MAX_MS=3000
TYPING_INDICATOR_ENABLED=true
N8N_ENABLED=false, N8N_WEBHOOK_URL, N8N_API_KEY
```

**Frontend** (`.env.local`):
```
DATABASE_URL=postgresql://...   # Direct Postgres (BetterAuth)
BETTER_AUTH_SECRET=...
RESEND_API_KEY=...
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000  # FastAPI backend
```

## Key Implementation Notes

**Collision detection is the core invariant**: `fromMe=true` on any `messages.upsert` event immediately sets `is_paused=true`. Before every LLM call, `is_paused` is re-checked. Never skip this check.

**Idempotency**: At the start of webhook processing, the `processed_events` table is checked. If `(tenant_id, message_id, event_type)` already exists, return early. This prevents duplicate LLM calls on Evolution API webhook retries.

**Message delays**: `MESSAGE_DELAY_ENABLED` adds a human-like random delay before sending to avoid WhatsApp bans. Configurable via `MESSAGE_DELAY_MIN_MS`/`MESSAGE_DELAY_MAX_MS`.

**n8n migration path**: Set `N8N_ENABLED=true` to route the AI reply step through an n8n workflow instead of the built-in LLM pipeline. The webhook handler has conditional branching for this.

**Tenant system prompt**: Each tenant in the `tenants` table has its own `system_prompt`. `DEFAULT_SYSTEM_PROMPT` from config is the fallback.

**Auto-resume**: `/cron/auto-resume` endpoint (secured with `CRON_SECRET`) resumes sessions where `last_human_at` is older than `RESUME_AFTER_HOURS`. Schedule `scripts/auto_resume.py` every 15 minutes (Railway cron or equivalent).

**Frontend auth flow**: The frontend gets a session token from `authClient.getSession()` and sends it as `Authorization: Bearer <token>` to FastAPI. FastAPI validates it against the `session` table — not JWTs.

## Current Status

**Backend** (~90% complete): All core endpoints implemented. Remaining: run `database/schema.sql` in Supabase, deploy to Railway, end-to-end testing.

**Frontend**: Built with all core pages (dashboard, instances, sessions, knowledge, settings) and auth flows. Shared components: `StatusBadge`, `DataTableKit` (TanStack Table), `TimelineComponent`.

**Reference docs**: `IMPLEMENTATION_STATUS.md`, `be_tasks.txt`, `fe_tasks.txt`, `plan.md`, `database/README.md`
