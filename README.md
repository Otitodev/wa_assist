# HybridFlow (WA Assist)

**Intelligent WhatsApp Automation with Collision Detection**

HybridFlow is a WhatsApp automation platform that prevents message conflicts when business owners manually intervene in AI-automated conversations. Built with FastAPI, Supabase, and Claude/GPT.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Supabase account (database)
- Evolution API instance (WhatsApp gateway)
- Anthropic API key or OpenAI API key

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/wa_assist.git
cd wa_assist

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Set up database
# Run database/schema.sql in Supabase SQL Editor

# Start server
uvicorn app.main:app --reload
```

### Test Installation

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {"ok": true, "version": "0.1.0", "checks": {...}}
```

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Complete deployment instructions for Railway |
| [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) | Current implementation status and remaining tasks |
| [database/README.md](database/README.md) | Database schema documentation and queries |
| [scripts/README.md](scripts/README.md) | Auto-resume script documentation |
| [CLAUDE.md](CLAUDE.md) | Codebase guide for AI assistants |
| [plan.md](plan.md) | Original implementation plan |

---

## 🎯 Features

### ✅ Completed (MVP)

**Core Functionality**:
- 🤖 Multi-LLM support (Anthropic Claude, OpenAI GPT)
- 📨 WhatsApp message processing via Evolution API
- 🚦 Collision detection (auto-pause on human intervention)
- ⏰ Auto-resume paused sessions after inactivity
- 🔄 Idempotency (prevents duplicate processing)

**Observability**:
- 📊 Structured JSON logging with context
- 🏥 Health checks with component status
- 🔍 Message event timeline

**APIs**:
- 👥 Tenant management
- 📱 Instance management
- 💬 Session management (pause/resume)
- 📝 Message/event queries

**Infrastructure**:
- 🌐 CORS support for frontend
- 🔐 Webhook authentication
- 🔄 Migration-ready for n8n orchestration
- 🚀 Railway deployment ready

### 🚧 Roadmap

- [ ] Frontend dashboard (Next.js + shadcn/ui)
- [ ] User authentication (JWT)
- [ ] Multi-user support
- [ ] Knowledge base integration
- [ ] Analytics & metrics
- [ ] Message templates
- [ ] Workflow builder (n8n integration)

---

## 🏗️ Architecture

### Current (MVP)
```
WhatsApp User
    ↓
Evolution API
    ↓
FastAPI Webhook
    ↓
LLM Provider (Claude/GPT)
    ↓
Evolution API (send reply)
    ↓
Supabase (state)
```

### Future (with n8n)
```
WhatsApp User
    ↓
Evolution API
    ↓
FastAPI Webhook (router)
    ↓
n8n Workflows
    ↓
LLM Provider + Custom Logic
    ↓
Evolution API (send reply)
    ↓
Supabase (state)
```

**Migration**: Simply set `N8N_ENABLED=true` - no code changes required!

---

## 🔌 API Endpoints

### Webhooks
- `POST /webhook/{instance}` - Evolution API webhook handler

### Health & Status
- `GET /health` - System health check

### Tenant Management
- `GET /api/tenants` - List all tenants
- `GET /api/tenants/{id}` - Get tenant details

### Instance Management
- `GET /api/instances?tenant_id=...` - List instances
- `GET /api/instances/{name}?tenant_id=...` - Get instance details
- `POST /api/instances/{name}/test-webhook` - Test Evolution connectivity

### Session Management
- `GET /api/sessions?tenant_id=...` - List sessions (with filters)
- `GET /api/sessions/{id}?tenant_id=...` - Get session details
- `POST /api/sessions/{id}/pause?tenant_id=...` - Pause session
- `POST /api/sessions/{id}/resume?tenant_id=...` - Resume session

### Messages
- `GET /api/events?tenant_id=...` - Get message timeline

### Cron Jobs
- `POST /cron/auto-resume` - Auto-resume paused sessions

### n8n Integration
- `POST /api/evolution/send-message` - Send message via Evolution API

---

## 💾 Database Schema

### Tables

**tenants** - Instance configuration
- `id`, `instance_name`, `evo_server_url`, `evo_api_key`
- `system_prompt`, `llm_provider`

**sessions** - Conversation state
- `id`, `tenant_id`, `chat_id`
- `is_paused`, `pause_reason`
- `last_message_at`, `last_human_at`

**messages** - Message history
- `id`, `tenant_id`, `chat_id`, `message_id`
- `from_me`, `message_type`, `text`, `raw`

**processed_events** - Idempotency tracking
- `id`, `tenant_id`, `message_id`, `event_type`
- `action_taken`, `processed_at`

See [database/README.md](database/README.md) for complete schema documentation.

---

## ⚙️ Configuration

### Environment Variables

```bash
# Database (required)
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"

# Security (required)
EVOLUTION_WEBHOOK_SHARED_SECRET="change-me"
CRON_SECRET="change-me-cron-secret"

# LLM Provider (required)
LLM_PROVIDER="anthropic"  # or "openai"
ANTHROPIC_API_KEY="sk-ant-..."
# OR
OPENAI_API_KEY="sk-..."

# CORS (optional)
CORS_ORIGINS="http://localhost:3000,https://your-frontend.vercel.app"

# Auto-resume (optional)
RESUME_AFTER_HOURS="2"

# n8n Integration (optional)
N8N_ENABLED="false"
N8N_WEBHOOK_URL="http://localhost:5678/webhook"
N8N_API_KEY="your-n8n-api-key"
```

See [.env.example](.env.example) for all available options.

---

## 🚀 Deployment

### Railway (Recommended)

1. **Setup Database**:
   ```bash
   # Run database/schema.sql in Supabase SQL Editor
   ```

2. **Deploy to Railway**:
   - Connect GitHub repository
   - Add environment variables
   - Railway auto-deploys on push

3. **Configure Webhook**:
   ```bash
   # Set Evolution API webhook URL
   POST https://your-evolution-api.com/webhook/set/{instance}
   {
     "url": "https://your-app.up.railway.app/webhook/{instance}",
     "events": ["MESSAGES_UPSERT", "MESSAGES_UPDATE"]
   }
   ```

4. **Setup Auto-Resume Cron**:
   - Railway cron job OR external scheduler
   - Endpoint: `POST /cron/auto-resume`
   - Schedule: Every 15 minutes

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed instructions.

---

## 🧪 Testing

### Manual Testing

```bash
# Health check
curl http://localhost:8000/health

# List tenants
curl http://localhost:8000/api/tenants

# List sessions
curl "http://localhost:8000/api/sessions?tenant_id=1"

# Pause session
curl -X POST "http://localhost:8000/api/sessions/1/pause?tenant_id=1"

# Test webhook (requires Evolution API)
curl -X POST "http://localhost:8000/api/instances/demo-instance/test-webhook?tenant_id=1"
```

### End-to-End Test

1. Send WhatsApp message to connected number
2. Verify AI reply received
3. Business owner sends message
4. Verify session paused
5. Wait 2 hours (or adjust RESUME_AFTER_HOURS)
6. Verify session auto-resumed

---

## 📊 Monitoring

### Logs

All logs are JSON-formatted with contextual fields:

```json
{
  "timestamp": "2026-01-23T14:00:00.000000+00:00",
  "level": "INFO",
  "message": "AI reply pipeline completed successfully",
  "tenant_id": 1,
  "chat_id": "5511999999999@s.whatsapp.net",
  "message_id": "ABC123",
  "action": "ai_replied",
  "duration_ms": 3245
}
```

### Key Metrics to Monitor

- **Webhook processing time**: `duration_ms` in logs
- **AI reply success rate**: Count `ai_replied` vs `ai_failed`
- **Session pause rate**: Count `paused` events
- **Auto-resume effectiveness**: Count sessions resumed

### Database Queries

```sql
-- Recent webhook activity
SELECT * FROM processed_events
ORDER BY processed_at DESC LIMIT 50;

-- Active sessions
SELECT * FROM sessions
WHERE is_paused = FALSE;

-- Message volume (last 24h)
SELECT COUNT(*) FROM messages
WHERE created_at > NOW() - INTERVAL '24 hours';
```

---

## 🛠️ Development

### Project Structure

```
wa_assist/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Environment configuration
│   ├── logger.py            # Structured logging
│   └── services/
│       ├── evolution_client.py       # Evolution API client
│       ├── llm_client.py            # LLM provider factory
│       └── llm_providers/
│           ├── base.py              # Abstract base class
│           ├── anthropic_provider.py # Anthropic implementation
│           └── openai_provider.py   # OpenAI implementation
├── database/
│   ├── schema.sql           # PostgreSQL schema
│   └── README.md           # Database documentation
├── scripts/
│   ├── auto_resume.py      # Auto-resume cron script
│   └── README.md           # Script documentation
├── requirements.txt        # Python dependencies
├── Procfile               # Railway deployment config
├── .env.example           # Environment variable template
├── DEPLOYMENT_GUIDE.md    # Deployment instructions
├── IMPLEMENTATION_STATUS.md # Development status
└── README.md             # This file
```

### Adding a New LLM Provider

1. Create `app/services/llm_providers/your_provider.py`:
   ```python
   from .base import BaseLLMProvider

   class YourProvider(BaseLLMProvider):
       async def generate_reply(self, message, system_prompt, context=None, **kwargs):
           # Your implementation
           pass
   ```

2. Register in `app/services/llm_client.py`:
   ```python
   def get_llm_provider(provider_name: str):
       if provider_name == "your_provider":
           return YourProvider()
       # ...
   ```

3. Add configuration to `app/config.py`:
   ```python
   YOUR_PROVIDER_API_KEY = os.getenv("YOUR_PROVIDER_API_KEY", "")
   ```

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **FastAPI** - High-performance Python web framework
- **Supabase** - Open-source Firebase alternative
- **Evolution API** - WhatsApp gateway
- **Anthropic Claude** - Advanced AI language model
- **OpenAI GPT** - AI language model

---

## 📞 Support

- 📚 [Documentation](DEPLOYMENT_GUIDE.md)
- 🐛 [Issue Tracker](https://github.com/yourusername/wa_assist/issues)
- 💬 [Discussions](https://github.com/yourusername/wa_assist/discussions)

---

## 🎯 Status

**Current Version**: 0.1.0 (MVP)
**Implementation**: 11/12 tasks completed (92%)
**Status**: Ready for deployment (database setup required)

See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for detailed progress.

---

Made with ❤️ by [Your Team Name]
