import os
from dotenv import load_dotenv

load_dotenv()

# Database
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# Server
API_PORT = int(os.getenv("API_PORT", "8000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

# Security
EVOLUTION_WEBHOOK_SHARED_SECRET = os.getenv("EVOLUTION_WEBHOOK_SHARED_SECRET", "change-me")
CRON_SECRET = os.getenv("CRON_SECRET", "change-me-cron-secret")

# Auto-resume configuration
RESUME_AFTER_HOURS = int(os.getenv("RESUME_AFTER_HOURS", "2"))

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

# LLM Provider Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")  # anthropic, openai, or custom
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "10"))

# Default system prompt if tenant doesn't have one
DEFAULT_SYSTEM_PROMPT = os.getenv(
    "DEFAULT_SYSTEM_PROMPT",
    "You are a helpful WhatsApp assistant. Respond professionally and concisely to customer inquiries."
)

# n8n Integration (for future workflow orchestration migration)
N8N_ENABLED = os.getenv("N8N_ENABLED", "false").lower() == "true"
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")
