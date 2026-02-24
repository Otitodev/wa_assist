# Whaply Database Schema

This directory contains database schema definitions and migration scripts for Supabase/PostgreSQL.

## Quick Start

### 1. Run Schema Setup

Open Supabase SQL Editor and run:

```bash
# In Supabase Dashboard:
# Go to SQL Editor → New Query → Paste contents of schema.sql → Run
```

Or use the Supabase CLI:

```bash
supabase db push --file database/schema.sql
```

### 2. Verify Tables Created

Run this query to verify all tables exist:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('tenants', 'sessions', 'messages', 'processed_events');
```

Expected result: 4 rows

### 3. Insert Test Tenant

```sql
INSERT INTO tenants (instance_name, evo_server_url, system_prompt, llm_provider)
VALUES (
    'demo-instance',
    'https://your-evolution-api.com',
    'You are a helpful WhatsApp assistant. Be professional and friendly.',
    'anthropic'
)
RETURNING *;
```

## Database Schema Overview

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `tenants` | WhatsApp instances/tenants | `instance_name`, `evo_server_url`, `system_prompt` |
| `sessions` | Conversation state tracking | `chat_id`, `is_paused`, `last_human_at` |
| `messages` | Message history | `message_id`, `from_me`, `text`, `raw` |
| `processed_events` | Idempotency tracking | `message_id`, `event_type`, `action_taken` |

### Key Indexes

**Performance Optimization:**
- `idx_tenants_instance_name` - Fast tenant lookup by instance name
- `idx_sessions_tenant_chat` - Fast session lookup
- `idx_sessions_paused_last_human` - Optimized for auto-resume queries (partial index on paused sessions)
- `idx_messages_tenant_msg` - Message deduplication
- `idx_processed_events_tenant_msg` - Idempotency check

**Auto-Resume Optimization:**
The partial index on `sessions(is_paused, last_human_at) WHERE is_paused = true` dramatically speeds up the auto-resume query by only indexing paused sessions.

### Unique Constraints

- `tenants.instance_name` - One record per instance
- `sessions(tenant_id, chat_id)` - One session per chat per tenant
- `messages(tenant_id, message_id)` - Prevents duplicate message storage
- `processed_events(tenant_id, message_id, event_type)` - Prevents duplicate event processing

## Database Functions

### cleanup_old_processed_events(days_to_keep)

Deletes old processed events to maintain database performance.

```sql
-- Delete events older than 7 days
SELECT cleanup_old_processed_events(7);

-- Delete events older than 30 days
SELECT cleanup_old_processed_events(30);
```

**Recommended:** Run this in auto_resume cron (already integrated).

### auto_resume_paused_sessions(hours_inactive)

Resumes sessions paused for longer than specified hours.

```sql
-- Resume sessions idle for more than 2 hours
SELECT auto_resume_paused_sessions(2);

-- Resume sessions idle for more than 6 hours
SELECT auto_resume_paused_sessions(6);
```

**Note:** The HTTP endpoint `/cron/auto-resume` already does this via Python.

## Column Details

### tenants

```sql
id                SERIAL        -- Auto-incrementing primary key
instance_name     VARCHAR(255)  -- Unique instance identifier from Evolution API
evo_server_url    VARCHAR(500)  -- Evolution API base URL
evo_api_key       VARCHAR(500)  -- Evolution API authentication key
system_prompt     TEXT          -- Custom AI persona/instructions for this tenant
llm_provider      VARCHAR(50)   -- LLM provider: 'anthropic', 'openai', etc
created_at        TIMESTAMPTZ   -- When tenant was created
updated_at        TIMESTAMPTZ   -- Last updated timestamp
```

### sessions

```sql
id                SERIAL        -- Auto-incrementing primary key
tenant_id         INTEGER       -- Foreign key to tenants.id
chat_id           VARCHAR(255)  -- WhatsApp chat ID (e.g., 5511999999999@s.whatsapp.net)
is_paused         BOOLEAN       -- True when human has taken over
pause_reason      VARCHAR(100)  -- 'human_takeover', 'manual_pause', etc
last_message_at   TIMESTAMPTZ   -- When last message was received in this chat
last_human_at     TIMESTAMPTZ   -- When business owner last sent a message (for auto-resume)
created_at        TIMESTAMPTZ   -- When session was first created
updated_at        TIMESTAMPTZ   -- Last updated timestamp
```

### messages

```sql
id                SERIAL        -- Auto-incrementing primary key
tenant_id         INTEGER       -- Foreign key to tenants.id
chat_id           VARCHAR(255)  -- WhatsApp chat ID
message_id        VARCHAR(255)  -- Unique message ID from Evolution API
from_me           BOOLEAN       -- True if sent by business owner or AI
message_type      VARCHAR(50)   -- 'conversation', 'image', 'video', etc
text              TEXT          -- Extracted text content
raw               JSONB         -- Full Evolution API payload (for debugging)
created_at        TIMESTAMPTZ   -- When message was stored
```

### processed_events

```sql
id                SERIAL        -- Auto-incrementing primary key
tenant_id         INTEGER       -- Foreign key to tenants.id
message_id        VARCHAR(255)  -- Message ID from webhook
event_type        VARCHAR(100)  -- 'messages.upsert', 'messages.update', etc
action_taken      VARCHAR(100)  -- 'paused', 'ai_replied', 'ignored_paused', etc
processed_at      TIMESTAMPTZ   -- When event was processed
```

## Common Queries

### Check for duplicate events

```sql
SELECT
    tenant_id,
    message_id,
    event_type,
    COUNT(*) as count
FROM processed_events
GROUP BY tenant_id, message_id, event_type
HAVING COUNT(*) > 1;
```

Expected result: 0 rows (no duplicates)

### View recent activity

```sql
SELECT
    pe.processed_at,
    t.instance_name,
    pe.message_id,
    pe.event_type,
    pe.action_taken
FROM processed_events pe
JOIN tenants t ON pe.tenant_id = t.id
ORDER BY pe.processed_at DESC
LIMIT 50;
```

### Find paused sessions ready for auto-resume

```sql
SELECT
    s.id,
    t.instance_name,
    s.chat_id,
    s.last_human_at,
    NOW() - s.last_human_at as idle_duration
FROM sessions s
JOIN tenants t ON s.tenant_id = t.id
WHERE s.is_paused = TRUE
  AND s.last_human_at < NOW() - INTERVAL '2 hours'
ORDER BY s.last_human_at ASC;
```

### Message statistics by tenant

```sql
SELECT
    t.instance_name,
    COUNT(*) FILTER (WHERE m.from_me = FALSE) as inbound_count,
    COUNT(*) FILTER (WHERE m.from_me = TRUE) as outbound_count,
    COUNT(*) as total_count
FROM messages m
JOIN tenants t ON m.tenant_id = t.id
WHERE m.created_at > NOW() - INTERVAL '24 hours'
GROUP BY t.instance_name
ORDER BY total_count DESC;
```

## Maintenance

### Cleanup old data

```sql
-- Clean up processed events older than 7 days
DELETE FROM processed_events
WHERE processed_at < NOW() - INTERVAL '7 days';

-- Archive old messages (move to archive table)
-- Create archive table first:
CREATE TABLE messages_archive (LIKE messages INCLUDING ALL);

-- Move messages older than 90 days
WITH deleted AS (
    DELETE FROM messages
    WHERE created_at < NOW() - INTERVAL '90 days'
    RETURNING *
)
INSERT INTO messages_archive
SELECT * FROM deleted;
```

### Database size monitoring

```sql
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Backup & Restore

### Backup (via Supabase CLI)

```bash
# Backup all data
supabase db dump -f backup.sql

# Backup schema only
supabase db dump --schema-only -f schema_backup.sql

# Backup data only
supabase db dump --data-only -f data_backup.sql
```

### Restore

```bash
# Restore from backup
supabase db reset
supabase db push --file backup.sql
```

## Troubleshooting

### "Table does not exist" error

Run `database/schema.sql` in Supabase SQL Editor.

### "Unique constraint violation"

Check for duplicate data before inserting. The unique constraints are:
- `tenants(instance_name)`
- `sessions(tenant_id, chat_id)`
- `messages(tenant_id, message_id)`
- `processed_events(tenant_id, message_id, event_type)`

### "Foreign key constraint violation"

Ensure referenced tenant exists before creating sessions/messages/events.

### Slow queries

Run `EXPLAIN ANALYZE` on slow queries to verify indexes are being used:

```sql
EXPLAIN ANALYZE
SELECT * FROM sessions
WHERE is_paused = TRUE
  AND last_human_at < NOW() - INTERVAL '2 hours';
```

Look for "Index Scan" in the output. If you see "Seq Scan", the index isn't being used.
