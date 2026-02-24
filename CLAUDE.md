# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Whaply** (WA Assist) - A full-stack SaaS platform for WhatsApp automation with intelligent human/AI collision detection. The system consists of:
- **Backend (FastAPI)**: Webhook ingestion, session state machine, multi-tenant persistence
- **Frontend (Next.js)**: Operational dashboard for monitoring sessions, managing knowledge base, and controlling automation
- **Core Value**: "Invisible Mute" - automatically pauses AI when business owners intervene, prevents message conflicts

## Architecture

### Core Components

**Webhook Ingestion Flow** (`app/main.py`)
- `POST /webhooks/evolution` - Primary webhook receiver for Evolution API events
- Resolves tenant by instance name
- Extracts message metadata via `evolve_parse.py` helpers
- Upserts session state on every inbound message
- Applies collision detection rules via `services/collision.py`

**Session State Machine** (database-driven)
- Sessions auto-create on first message per chat
- `is_paused=true` set immediately when business owner sends message (`fromMe=true`)
- AI replies blocked while paused
- Auto-resume after 2 hours of inactivity (via cronjob, see `cronjob.txt`)

**Data Flow**
1. Evolution API webhook → `/webhooks/evolution`
2. Tenant lookup by `instance_name` in `tenants` table
3. Message stored in `messages` table (deduped by `tenant_id + message_id`)
4. Session upserted in `sessions` table with `last_message_at` timestamp
5. Collision rule evaluated: if `fromMe=true` → pause session
6. If not paused and inbound message → placeholder returns `enqueue_ai` (AI reply pipeline not yet implemented)

### Module Responsibilities

**`app/config.py`**
- Loads environment variables via `python-dotenv`
- Required: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- Optional: `API_PORT` (default 8000), `LOG_LEVEL` (default info)

**`app/db.py`**
- Initializes Supabase client with service role key
- Raises `RuntimeError` if credentials missing

**`app/evolve_parse.py`**
- Extracts fields from Evolution API webhook payloads
- Handles nested structure: `payload.data.key.{remoteJid, id, fromMe}`
- Message text extraction supports `conversation` and `extendedTextMessage` types

**`app/services/collision.py`**
- `should_pause_on_event()` - Returns `true` if `messages.upsert` with `fromMe=true`
- `now_utc()` - Helper for consistent UTC timestamps

**`app/models.py`**
- Currently scaffolded with `BaseModel` (SQLAlchemy base with common fields)
- Not actively used; persistence handled via Supabase client directly

### Database Schema

**Tables (Supabase/Postgres)**
- `tenants` - Maps `instance_name` to tenant config (includes `evo_server_url`)
- `sessions` - Tracks conversation state: `tenant_id`, `chat_id`, `is_paused`, `last_message_at`, `last_human_at`, `pause_reason`
- `messages` - Stores all inbound messages with `raw` JSON payload, deduped by `(tenant_id, message_id)`

**Constraints**
- Sessions: unique on `(tenant_id, chat_id)`
- Messages: unique on `(tenant_id, message_id)`

### Frontend Architecture (Next.js Dashboard)

**Tech Stack**
- Next.js 14+ with App Router
- TypeScript
- Tailwind CSS
- shadcn/ui component library
- TanStack Table for data tables
- Zod for API response validation

**Design System: "Whaply UI"**
- WhatsApp-inspired but professional (not a clone)
- Brand colors: Deep green (primary), teal/emerald (secondary)
- Visual principles: Operational product feel, fast scanning, clear state indicators
- Trust cues: System health indicators, last event timestamps, webhook status

**Core Pages & Routes**
- `/dashboard` - KPI cards (Active/Paused chats, AI replies, interference rate), health status, recent activity feed
- `/instances` - List view of WhatsApp instances with status, webhook config, last seen
  - `/instances/[name]` - Detail view with tabs (Overview, Webhooks, Logs), test webhook button
- `/sessions` - **Critical page**: Table of all chat sessions with Active/Paused state, filters, search
  - `/sessions/[id]` - **State machine view**: Timeline of messages/events, manual pause/resume controls, debug panel
- `/knowledge` - Upload PDF/DOC/TXT, edit persona/prompt, version history
- `/alerts` - Rules builder for sentiment thresholds, keyword triggers, escalations
- `/settings` - Tenant config, API keys management, webhook endpoints

**Key UI Components**
- `StatusBadge` - Standardized badges for Active/Paused/Error/Connecting states
- `DataTableKit` - TanStack Table wrapper with column visibility, sticky headers, skeleton loading
- `TimelineComponent` - Event feed showing inbound/outbound messages, state changes, errors
- `HealthPill` - Shows webhook health, last event age, error rates

**Frontend ↔ Backend API Contract**

Sessions API:
- `GET /api/sessions?tenantId=&instance=&state=&q=&page=` - List sessions with filters
- `GET /api/sessions/:sessionId?tenantId=` - Get session details
- `POST /api/sessions/:sessionId/pause` - Manually pause session
- `POST /api/sessions/:sessionId/resume` - Manually resume session

Instances API:
- `GET /api/instances?tenantId=` - List WhatsApp instances
- `GET /api/instances/:instanceName?tenantId=` - Get instance details
- `POST /api/instances/:instanceName/test-webhook` - Test webhook connectivity

Tenants API:
- `GET /api/tenants` - List tenants for current user
- `GET /api/tenants/:tenantId` - Get tenant details

Events API:
- `GET /api/events?tenantId=&instance=&sessionId=&limit=` - Get event timeline

Knowledge API:
- `POST /api/knowledge/upload` - Upload knowledge base files
- `PUT /api/knowledge/prompt` - Update AI persona/prompt
- `GET /api/knowledge/versions` - List prompt versions

Alerts API:
- `GET/POST/PUT/DELETE /api/alerts-rules` - CRUD for alert rules

**Frontend State Management**
- Tenant context: Active tenant selected via topbar switcher, persisted to localStorage
- Auth state: Route guards redirect unauthed users to `/login`
- API client: Centralized fetch wrapper with Zod validation, consistent error handling

## Development Commands

### Backend (FastAPI)

**Environment Setup**
```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Unix)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Then edit .env with actual Supabase credentials
```

**Running the Backend**
```bash
# Run FastAPI server with hot reload
uvicorn app.main:app --reload --port 8000

# Health check
curl http://localhost:8000/health

# View API docs
# Navigate to http://localhost:8000/docs (Swagger UI)
```

**Testing Backend Endpoints**
```bash
# Get session status
curl http://localhost:8000/sessions/{instance_name}/{chat_id}

# Manually resume a paused session
curl -X POST http://localhost:8000/sessions/{instance_name}/{chat_id}/resume

# Test webhook (send sample Evolution API payload)
curl -X POST http://localhost:8000/webhooks/evolution \
  -H "Content-Type: application/json" \
  -d '{"event":"messages.upsert","instance":"test","data":{...}}'
```

**Code Quality (Backend)**
```bash
# Format code
black app/

# Lint
flake8 app/

# Type checking
mypy app/

# Run tests
pytest

# Run specific test file
pytest tests/test_collision.py
```

### Frontend (Next.js)

**Setup**
```bash
# Navigate to frontend directory (when created)
cd frontend

# Install dependencies
npm install
# or
pnpm install

# Copy environment template
cp .env.local.example .env.local
# Configure NEXT_PUBLIC_API_URL to point to FastAPI backend
```

**Running the Frontend**
```bash
# Development server with hot reload
npm run dev
# Typically runs on http://localhost:3000

# Production build
npm run build

# Start production server
npm run start
```

**Code Quality (Frontend)**
```bash
# Lint
npm run lint

# Format with Prettier
npm run format

# Type check
npm run type-check

# Run tests
npm run test
```

**shadcn/ui Commands**
```bash
# Add new shadcn component
npx shadcn@latest add button
npx shadcn@latest add table
npx shadcn@latest add dialog

# Add multiple components at once
npx shadcn@latest add button input label card
```

## Key Implementation Patterns

### Collision Detection (Core Value Prop)
The system prevents AI/human message conflicts:
- **Pause trigger**: `messages.upsert` event where `fromMe=true`
- **Pause effect**: Session `is_paused` set to `true`, `last_human_at` updated
- **AI gate**: Before generating reply, check `is_paused` status
- **Auto-resume**: Cron runs SQL in `cronjob.txt` every N minutes to unpause sessions idle >2 hours

### Idempotency
- Message deduplication via `message_id` prevents duplicate processing on webhook retries
- Session upserts use `on_conflict` to avoid errors

### Multi-Tenancy
- All queries filter by `tenant_id` resolved from Evolution `instance` name
- Each tenant can have separate Evolution server URL and credentials

### Frontend UX Patterns

**Loading Strategy (Skeleton-First)**
- Use skeleton states for cards, tables, and timelines
- Prevent layout shifts during data fetching
- Show loading state immediately on navigation

**Empty States**
- Every empty state must have a clear next action CTA
- Examples:
  - No instances → "Connect WhatsApp" button
  - No knowledge base → "Upload knowledge" button
  - Paused sessions exist → "Review paused chats" link

**Status Indication**
- Active sessions: Filled green badge
- Paused sessions: Outlined yellow/orange badge
- Error states: Red badge with error icon
- Connection states: Neutral gray badge with spinner

**Session Detail Page (Most Critical UI)**
- Timeline shows complete conversation history with state changes
- Manual pause/resume controls prominent at top
- Debug panel shows raw session JSON and webhook payloads
- Real-time updates when session state changes

**Table Design (Compact, Scannable)**
- Sticky headers for long tables
- Column sorting on key fields (state, lastSeen, lastMessage)
- Filter chips for quick filtering (state, instance, time range)
- Row click opens detail view
- Pagination or infinite scroll for large datasets

## Current State & Next Steps

**Backend: Implemented (MVP Core)**
- ✅ Webhook ingestion for Evolution API (`/webhooks/evolution`)
- ✅ Tenant resolution by instance name
- ✅ Session state tracking with pause/resume
- ✅ Pause-on-human-intervention logic (collision detection)
- ✅ Message persistence with deduplication
- ✅ Manual resume endpoint
- ✅ Session status endpoint

**Backend: Not Yet Implemented**
- ⏳ AI reply generation pipeline (placeholder returns `enqueue_ai`)
- ⏳ Outbound message sending via Evolution API
- ⏳ Webhook authentication/signature verification
- ⏳ Async job queue (Redis/Celery for AI processing)
- ⏳ Auto-resume cronjob deployment (SQL ready in `cronjob.txt`)
- ⏳ Additional API endpoints for frontend dashboard (instances, events, knowledge, alerts)

**Frontend: Not Yet Started**
- ⏳ Next.js project bootstrap with App Router
- ⏳ shadcn/ui setup and Whaply theme
- ⏳ Global layout shell (sidebar, topbar)
- ⏳ Authentication UI
- ⏳ Core pages: Dashboard, Instances, Sessions (critical), Knowledge, Alerts, Settings
- ⏳ Reusable components: StatusBadge, DataTableKit, TimelineComponent
- ⏳ API client with Zod validation

**Recommended Build Order**

Backend (Next 2 Sprints):
1. HF-040, HF-041 - Outbound messaging + AI reply pipeline
2. Extend API endpoints for dashboard (sessions list, instances list, events)
3. Deploy auto-resume cronjob

Frontend (Start After Backend APIs Ready):
1. UI-001, UI-002, UI-003 - Project setup, layout, theme
2. UI-200, UI-201 - Core components (StatusBadge, DataTableKit)
3. UI-100 - Dashboard overview
4. UI-110, UI-111 - Instances pages
5. UI-120, UI-121, UI-202 - Sessions pages + timeline (most important)
6. UI-130 - Knowledge base
7. UI-150 - Settings
8. UI-140 - Alerts

**Reference Documents**
- `be_tasks.txt` - Backend engineering tickets (HF-001 through HF-071)
- `fe_tasks.txt` - Frontend engineering tickets (UI-001 through UI-402)
- `plan.md` - High-level project roadmap
- `cronjob.txt` - SQL for auto-resume logic (needs scheduling in production)

## Important Notes

**Backend**
- **Session state is source of truth**: Always query `sessions` table to determine if AI should reply
- **fromMe detection is critical**: Evolution API uses `fromMe=true` to indicate business owner sent the message
- **Supabase service role key required**: App bypasses RLS policies; ensure key is properly secured
- **Chat IDs from Evolution**: Format is `{phone_number}@s.whatsapp.net` for individual chats, different for groups
- **Webhook idempotency**: Use `message_id` for deduplication; Evolution may retry failed webhooks

**Frontend**
- **shadcn/ui is the primary component source**: Don't build from scratch what shadcn provides
- **Whaply theme tokens**: Use CSS variables defined in `theme.css`, don't hardcode colors
- **Session page is mission-critical**: This is where users monitor and control the collision detection
- **API contract must match backend**: Coordinate endpoint shapes before implementing UI
- **Multi-tenant context**: Always include `tenantId` in API requests; use tenant switcher to change context
- **Real-time considerations**: Session state changes may need polling or WebSocket updates for live dashboard

**Integration**
- Backend currently on port 8000, frontend will typically run on port 3000 in development
- CORS must be configured in FastAPI to allow frontend origin
- Frontend API client should use `NEXT_PUBLIC_API_URL` environment variable
