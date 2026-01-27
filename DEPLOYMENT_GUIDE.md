# HybridFlow Deployment Guide

This guide walks through deploying the HybridFlow backend to Railway (or any similar platform).

---

## Prerequisites

- [ ] Supabase project created with schema applied (see Database Setup section)
- [ ] Evolution API instance configured and running
- [ ] Anthropic API key (or OpenAI API key)
- [ ] Railway account (or alternative hosting platform)

---

## Step 1: Database Setup (Supabase)

### 1.1 Run Schema

1. Open Supabase Dashboard → SQL Editor
2. Click "New Query"
3. Paste contents of `database/schema.sql`
4. Click "Run" to execute

**Expected output**: 4 tables created (tenants, sessions, messages, processed_events)

### 1.2 Verify Tables Created

Run this query to verify:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('tenants', 'sessions', 'messages', 'processed_events');
```

**Expected**: 4 rows returned

### 1.3 Insert Test Tenant

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

Replace `your-evolution-api.com` with your actual Evolution API URL.

### 1.4 Get Supabase Credentials

In Supabase Dashboard → Settings → API:
- Copy **Project URL** (SUPABASE_URL)
- Copy **service_role key** (SUPABASE_SERVICE_ROLE_KEY)

**⚠️ Important**: Never commit service_role key to git. Use environment variables only.

---

## Step 2: Prepare for Deployment

### 2.1 Create Procfile

Create `Procfile` in repository root:

```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**What this does**: Tells Railway (or Heroku) how to start the FastAPI server.

### 2.2 Verify Requirements

Ensure `requirements.txt` contains all dependencies:

```txt
fastapi==0.115.0
uvicorn==0.30.6
pydantic==2.8.2
python-dotenv==1.0.1
supabase==2.6.0
httpx==0.27.2
sqlalchemy>=2.0.0
anthropic>=0.25.0
openai>=1.30.0
```

### 2.3 Test Locally (Optional)

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (create .env file)
cp .env.example .env
# Edit .env with your actual values

# Run server
uvicorn app.main:app --reload

# Test health endpoint
curl http://localhost:8000/health
```

**Expected response**:
```json
{
  "ok": true,
  "version": "0.1.0",
  "timestamp": "2026-01-23T...",
  "checks": {
    "database": {"status": "ok", "message": "Connected to Supabase"},
    "llm": {"status": "ok", "message": "LLM provider configured"}
  }
}
```

---

## Step 3: Deploy to Railway

### 3.1 Create Railway Project

1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Connect your GitHub account and select the repository
5. Railway will auto-detect Python and start building

### 3.2 Configure Environment Variables

In Railway Dashboard → Variables, add the following:

**Required Variables**:
```bash
# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here

# Security
EVOLUTION_WEBHOOK_SHARED_SECRET=your-secure-secret-here
CRON_SECRET=your-cron-secret-here

# LLM Provider
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# CORS (add your frontend domain)
CORS_ORIGINS=http://localhost:3000,https://your-frontend.vercel.app
```

**Optional Variables**:
```bash
# Server
API_PORT=8000
LOG_LEVEL=info

# Auto-resume
RESUME_AFTER_HOURS=2

# LLM Configuration
LLM_MAX_TOKENS=1024
LLM_TIMEOUT=10
DEFAULT_SYSTEM_PROMPT=You are a helpful WhatsApp assistant.

# n8n Integration (if using)
N8N_ENABLED=false
N8N_WEBHOOK_URL=http://localhost:5678/webhook
N8N_API_KEY=your-n8n-api-key
```

**⚠️ Security Notes**:
- Generate strong random secrets for EVOLUTION_WEBHOOK_SHARED_SECRET and CRON_SECRET
- Never commit secrets to git
- Use Railway's secret management (variables are encrypted at rest)

### 3.3 Deploy

1. Railway will automatically deploy after you add environment variables
2. Wait for build to complete (2-3 minutes)
3. Note the deployment URL: `https://your-app.up.railway.app`

### 3.4 Verify Deployment

Test the health endpoint:

```bash
curl https://your-app.up.railway.app/health
```

**Expected response**:
```json
{
  "ok": true,
  "version": "0.1.0",
  "checks": {
    "database": {"status": "ok"},
    "llm": {"status": "ok"}
  }
}
```

If `ok: false`, check Railway logs:
```bash
# In Railway Dashboard → Logs
# Look for error messages
```

---

## Step 4: Configure Evolution API Webhook

### 4.1 Set Webhook URL

In Evolution API, set webhook URL for your instance:

```bash
POST https://your-evolution-api.com/webhook/set/{instance_name}
Content-Type: application/json

{
  "url": "https://your-app.up.railway.app/webhook/{instance_name}",
  "webhook_by_events": false,
  "webhook_base64": false,
  "events": [
    "QRCODE_UPDATED",
    "MESSAGES_UPSERT",
    "MESSAGES_UPDATE",
    "CONNECTION_UPDATE"
  ]
}
```

**Note**: Replace `{instance_name}` with your actual instance name (e.g., `demo-instance`).

### 4.2 Test Webhook

Send a test WhatsApp message to the number associated with your instance.

**What should happen**:
1. Evolution API receives message
2. Evolution API sends webhook to your FastAPI backend
3. FastAPI processes webhook and generates AI reply
4. Evolution API sends reply back to WhatsApp user

**Check Railway logs** to verify:
```
{"level": "INFO", "message": "Webhook received", "event": "messages.upsert", ...}
{"level": "INFO", "message": "AI reply pipeline completed successfully", ...}
```

---

## Step 5: Set Up Auto-Resume Cron Job

You have two options:

### Option A: Railway Cron Job (Recommended)

1. In Railway Dashboard, click "New" → "Empty Service"
2. Name it: `auto-resume-cron`
3. Settings → Build → Build Command: (leave empty)
4. Settings → Deploy → Start Command: `python scripts/auto_resume.py`
5. Settings → Cron → Schedule: `*/15 * * * *` (every 15 minutes)
6. Variables → Add same environment variables as main app:
   - SUPABASE_URL
   - SUPABASE_SERVICE_ROLE_KEY
   - RESUME_AFTER_HOURS

**How it works**: Railway runs the script every 15 minutes automatically.

### Option B: External Cron (Cloud Scheduler, cron-job.org)

If using Google Cloud Scheduler:

1. Create new scheduled job
2. Target: HTTP
3. URL: `https://your-app.up.railway.app/cron/auto-resume`
4. Method: POST
5. Headers:
   - `X-Cron-Secret: your-cron-secret-here` (must match CRON_SECRET env var)
6. Schedule: `*/15 * * * *` (every 15 minutes)

If using cron-job.org:

1. Go to https://cron-job.org
2. Create new cron job
3. URL: `https://your-app.up.railway.app/cron/auto-resume`
4. Schedule: Every 15 minutes
5. HTTP Method: POST
6. HTTP Headers:
   - `X-Cron-Secret: your-cron-secret-here`

### Verify Auto-Resume Works

1. Manually pause a session:
   ```bash
   curl -X POST "https://your-app.up.railway.app/api/sessions/1/pause?tenant_id=1"
   ```

2. Check session status:
   ```bash
   curl "https://your-app.up.railway.app/api/sessions/1?tenant_id=1"
   ```

3. Wait for cron to run (or trigger manually)

4. Check session status again - `is_paused` should be `false`

---

## Step 6: Configure Frontend (Optional)

If deploying the Next.js frontend:

1. Deploy frontend to Vercel/Netlify
2. Set environment variable:
   ```
   NEXT_PUBLIC_API_URL=https://your-app.up.railway.app
   ```

3. Update backend CORS_ORIGINS to include frontend domain:
   ```
   CORS_ORIGINS=http://localhost:3000,https://your-frontend.vercel.app
   ```

---

## Troubleshooting

### Issue: Health check returns 500 or `ok: false`

**Solution**:
1. Check Railway logs for errors
2. Verify SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are correct
3. Verify database tables exist (run schema.sql)
4. Check LLM API key is valid (ANTHROPIC_API_KEY or OPENAI_API_KEY)

### Issue: Webhook not received

**Solution**:
1. Verify Evolution API webhook URL is correct
2. Check EVOLUTION_WEBHOOK_SHARED_SECRET matches on both sides
3. Check Railway logs for incoming requests
4. Test with curl:
   ```bash
   curl -X POST "https://your-app.up.railway.app/webhook/demo-instance" \
     -H "Content-Type: application/json" \
     -d '{"event": "messages.upsert", "data": {"key": {"remoteJid": "5511999999999@s.whatsapp.net"}}}'
   ```

### Issue: AI replies not sent

**Solution**:
1. Check Railway logs for "AI reply pipeline" messages
2. Verify LLM_PROVIDER is set correctly (anthropic/openai)
3. Verify API key is valid
4. Check tenant has system_prompt configured in database
5. Verify Evolution API connection (test with `/api/instances/{name}/test-webhook`)

### Issue: Sessions not auto-resuming

**Solution**:
1. Verify cron job is running (check Railway cron logs or external scheduler)
2. Verify CRON_SECRET matches in environment and request headers
3. Check logs for "Auto-resumed N sessions" message
4. Verify last_human_at timestamp is older than RESUME_AFTER_HOURS
5. Test endpoint manually:
   ```bash
   curl -X POST "https://your-app.up.railway.app/cron/auto-resume" \
     -H "X-Cron-Secret: your-cron-secret-here"
   ```

### Issue: CORS errors from frontend

**Solution**:
1. Verify frontend domain is in CORS_ORIGINS environment variable
2. Use full URL including protocol (https://)
3. For development, include http://localhost:3000
4. Restart Railway app after changing CORS_ORIGINS

### Issue: Database connection errors

**Solution**:
1. Verify Supabase project is not paused (free tier projects pause after inactivity)
2. Check SUPABASE_URL format: `https://xxx.supabase.co` (no trailing slash)
3. Verify service_role key has full permissions
4. Check Supabase dashboard → Settings → API for correct credentials

---

## Monitoring & Observability

### View Logs

**Railway Dashboard → Logs**:
- Real-time log streaming
- Filter by log level (INFO, WARNING, ERROR)
- All logs are JSON-formatted with contextual fields

**Key log events to monitor**:
- `"action": "webhook_received"` - Incoming webhooks
- `"action": "ai_replied"` - Successful AI responses
- `"action": "paused"` - Session paused (human takeover)
- `"action": "ai_failed"` - LLM errors
- `"action": "evolution_send_failed"` - Evolution API errors

### Health Monitoring

Set up uptime monitoring (e.g., UptimeRobot, Pingdom):
- URL: `https://your-app.up.railway.app/health`
- Interval: Every 5 minutes
- Alert if `ok: false` or status code != 200

### Database Monitoring

**Supabase Dashboard → Database**:
- Monitor table sizes
- Check query performance
- View recent queries
- Set up alerts for high CPU/memory usage

**Useful queries**:

1. Recent webhook activity:
```sql
SELECT * FROM processed_events
ORDER BY processed_at DESC
LIMIT 50;
```

2. Active sessions:
```sql
SELECT * FROM sessions
WHERE is_paused = FALSE
ORDER BY last_message_at DESC;
```

3. Paused sessions ready for resume:
```sql
SELECT * FROM sessions
WHERE is_paused = TRUE
  AND last_human_at < NOW() - INTERVAL '2 hours';
```

4. Message volume by tenant:
```sql
SELECT
  t.instance_name,
  COUNT(*) as message_count,
  COUNT(*) FILTER (WHERE m.from_me = FALSE) as inbound_count,
  COUNT(*) FILTER (WHERE m.from_me = TRUE) as outbound_count
FROM messages m
JOIN tenants t ON m.tenant_id = t.id
WHERE m.created_at > NOW() - INTERVAL '24 hours'
GROUP BY t.instance_name;
```

---

## Scaling Considerations

### Current Architecture (MVP)
- **Stateless**: FastAPI is stateless, can scale horizontally
- **Synchronous**: Webhook waits for LLM response (3-5s)
- **Direct**: FastAPI handles everything

**Limitations**:
- LLM timeout = 10s (could block webhook if provider is slow)
- High volume could overwhelm single instance

### Future Scaling Options

**Option 1: Horizontal Scaling**
- Railway auto-scaling: Scale to multiple instances based on CPU/memory
- Add load balancer (Railway provides this automatically)
- Keep stateless design

**Option 2: n8n Migration**
- Set `N8N_ENABLED=true`
- Offload LLM processing to n8n workflows
- FastAPI becomes lightweight webhook router
- n8n handles retries, rate limiting, workflow orchestration

**Option 3: Message Queue**
- Add Redis/RabbitMQ for async processing
- Webhook accepts message → queue → worker processes
- Faster webhook response times
- Better handling of spikes

**Option 4: Database Optimization**
- Add read replicas for queries
- Implement caching (Redis) for tenant configs
- Archive old messages to separate table

---

## Security Best Practices

### 1. Secrets Management
- ✅ Use Railway environment variables (encrypted at rest)
- ✅ Never commit secrets to git
- ✅ Rotate secrets regularly (every 90 days)
- ✅ Use strong random secrets (32+ characters)

### 2. API Security
- ✅ Webhook authentication via EVOLUTION_WEBHOOK_SHARED_SECRET
- ✅ Cron endpoint authentication via CRON_SECRET
- ⚠️ TODO: Add authentication to frontend APIs (JWT, session-based)
- ⚠️ TODO: Add rate limiting to prevent abuse

### 3. Database Security
- ✅ Use service_role key (full permissions for backend only)
- ✅ Never expose service_role key to frontend
- ⚠️ TODO: Implement Row Level Security (RLS) policies in Supabase
- ⚠️ TODO: Add database backups (Supabase does this automatically)

### 4. CORS Configuration
- ✅ Restrict CORS_ORIGINS to known domains
- ✅ Use HTTPS in production
- ⚠️ TODO: Remove localhost from CORS_ORIGINS in production

### 5. Input Validation
- ✅ Pydantic models validate request bodies
- ✅ SQL injection prevented by Supabase client
- ⚠️ TODO: Add input sanitization for user-generated content
- ⚠️ TODO: Implement content moderation for AI responses

---

## Post-Deployment Checklist

- [ ] Database schema applied successfully
- [ ] FastAPI server deployed and accessible
- [ ] Health endpoint returns 200 with `ok: true`
- [ ] Evolution API webhook configured
- [ ] Test WhatsApp message → AI reply received
- [ ] Business owner message → Session paused
- [ ] Auto-resume cron job configured and running
- [ ] Logs visible in Railway dashboard
- [ ] CORS configured for frontend domain (if applicable)
- [ ] Uptime monitoring set up
- [ ] Error alerting configured
- [ ] Secrets rotated from default values
- [ ] Documentation updated with production URLs

---

## Support & Resources

- **Implementation Status**: See `IMPLEMENTATION_STATUS.md`
- **Database Documentation**: See `database/README.md`
- **Auto-Resume Documentation**: See `scripts/README.md`
- **Codebase Guide**: See `CLAUDE.md`
- **Railway Documentation**: https://docs.railway.app
- **Supabase Documentation**: https://supabase.com/docs
- **FastAPI Documentation**: https://fastapi.tiangolo.com

---

## Rollback Procedure

If deployment fails or causes issues:

1. **Revert to previous Railway deployment**:
   - Railway Dashboard → Deployments → Select previous deployment → "Rollback"

2. **Revert database changes** (if schema was modified):
   ```bash
   # Backup current state
   supabase db dump -f backup_before_rollback.sql

   # Restore previous backup
   supabase db reset
   supabase db push --file previous_backup.sql
   ```

3. **Revert environment variables**:
   - Railway Dashboard → Variables → Restore previous values

4. **Investigate logs**:
   - Check Railway logs for error messages
   - Check Supabase logs for database errors
   - Check Evolution API logs for webhook issues

5. **Fix and redeploy**:
   - Fix issues locally
   - Test thoroughly
   - Deploy again
