# HybridFlow Scripts

This directory contains standalone scripts for scheduled tasks, maintenance, and development.

## seed_data.py

Populates the database with sample data for development and testing.

### Usage

```bash
# Seed data (adds to existing)
python scripts/seed_data.py

# Clean and re-seed (WARNING: deletes ALL existing data first)
python scripts/seed_data.py --clean
```

### What It Creates

| Table | Records | Description |
|-------|---------|-------------|
| tenants | 3 | Demo, Support, and Sales instances with different configs |
| sessions | 8 | Mix of active and paused conversations |
| messages | 20 | Sample conversation threads (product inquiry, support, etc.) |
| processed_events | 10 | Idempotency tracking records |

### Sample Tenants

| Instance Name | LLM Provider | Description |
|--------------|--------------|-------------|
| demo-instance | anthropic | General customer service bot |
| support-bot | anthropic | Technical support assistant |
| sales-assistant | openai | Sales and pricing inquiries |

### Configuration

Requires environment variables in `.env`:
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key

### Sample Data Characteristics

**Sessions**:
- Distributed across all 3 tenants
- ~33% are paused (simulating human intervention)
- Varied timestamps for realistic testing

**Messages**:
- 4 complete conversation threads
- Mix of inbound (customer) and outbound (AI/human) messages
- Realistic scenarios: product inquiry, support issue, quick question, human takeover

### After Seeding

Test the API:
```bash
# List all tenants
curl http://localhost:8000/api/tenants

# List sessions for tenant 1
curl "http://localhost:8000/api/sessions?tenant_id=1"

# Get events/messages for a session
curl "http://localhost:8000/api/events?tenant_id=1&session_id=1"
```

---

## auto_resume.py

Automatically resumes sessions that have been paused due to human takeover after a configurable period of inactivity.

### Configuration

Environment variables:
- `RESUME_AFTER_HOURS` - Hours of inactivity before auto-resume (default: 2)
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key

### Usage

#### Manual Execution

```bash
# From repository root
python scripts/auto_resume.py
```

#### Cron Job (Linux/Mac)

Add to crontab to run every 15 minutes:

```bash
# Edit crontab
crontab -e

# Add this line (runs every 15 minutes)
*/15 * * * * cd /path/to/wa_assist && /path/to/wa_assist/venv/bin/python scripts/auto_resume.py >> /var/log/auto_resume.log 2>&1
```

#### Railway Cron Service

Create a separate Railway service:

1. Service name: `auto-resume-cron`
2. Build command: (none)
3. Start command: `python scripts/auto_resume.py`
4. Add cron schedule: `*/15 * * * *` (every 15 minutes)
5. Add same environment variables as main app

#### Cloud Run Scheduled Task (Google Cloud)

1. Create Cloud Scheduler job
2. Target: HTTP
3. URL: `https://your-app.run.app/cron/auto-resume`
4. Method: POST
5. Headers:
   - `X-Cloudscheduler-Token: <your-CRON_SECRET>`
6. Schedule: `*/15 * * * *` (every 15 minutes)

#### HTTP Endpoint (Alternative)

Instead of running the script directly, call the HTTP endpoint:

```bash
curl -X POST https://your-app.run.app/cron/auto-resume \
  -H "X-Cron-Secret: your-secret-here"
```

Response:
```json
{
  "ok": true,
  "resumed_count": 5,
  "cleaned_up_events": 123,
  "cutoff_time": "2026-01-23T12:00:00.000000+00:00"
}
```

### What It Does

1. **Resumes paused sessions**: Finds sessions where `is_paused=true` and `last_human_at` is older than `RESUME_AFTER_HOURS`
2. **Cleans up old events**: Deletes `processed_events` records older than 7 days (helps maintain database performance)
3. **Logs activity**: Outputs detailed logs for monitoring

### Monitoring

Check logs for:
- Number of sessions resumed
- Any errors during execution
- Cleanup statistics

Example output:
```
============================================================
HybridFlow Auto-Resume Script
Timestamp: 2026-01-23T14:00:00.000000+00:00
============================================================
Auto-resuming sessions paused before 2026-01-23T12:00:00.000000+00:00 (2 hours ago)
Found 3 sessions to resume:
  - Session 1: tenant_id=1, chat_id=5511999999999@s.whatsapp.net, last_human_at=2026-01-23T10:30:00Z
  - Session 2: tenant_id=1, chat_id=5511888888888@s.whatsapp.net, last_human_at=2026-01-23T11:15:00Z
  - Session 3: tenant_id=2, chat_id=5511777777777@s.whatsapp.net, last_human_at=2026-01-23T09:45:00Z
✓ Successfully resumed 3 sessions
✓ Cleaned up 45 old processed events (>7 days)
============================================================
Done. Resumed 3 sessions.
============================================================
```

### Recommended Schedule

- **Every 15 minutes**: Recommended for production (balances responsiveness vs. database load)
- **Every 30 minutes**: Acceptable for low-traffic environments
- **Every 5 minutes**: Only if you need very responsive auto-resume (increases database queries)

### Troubleshooting

**Script fails with "SUPABASE_URL not set"**
- Ensure `.env` file exists or environment variables are set in your cron/scheduler

**No sessions being resumed**
- Check that sessions exist with `is_paused=true`
- Verify `last_human_at` timestamp is older than `RESUME_AFTER_HOURS`
- Check Supabase connectivity

**Database errors**
- Verify `SUPABASE_SERVICE_ROLE_KEY` has permission to update sessions table
- Check that `sessions` table exists with correct schema
