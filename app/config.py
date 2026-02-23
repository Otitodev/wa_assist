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
BETTER_AUTH_SECRET = os.getenv("BETTER_AUTH_SECRET", "")

# Auto-resume configuration
RESUME_AFTER_HOURS = int(os.getenv("RESUME_AFTER_HOURS", "2"))

# CORS - supports multiple origins comma-separated
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

# WebSocket Configuration (alternative to webhooks)
WEBSOCKET_ENABLED = os.getenv("WEBSOCKET_ENABLED", "false").lower() == "true"
WEBSOCKET_MODE = os.getenv("WEBSOCKET_MODE", "global")  # "global" or "instance"
EVOLUTION_SERVER_URL = os.getenv("EVOLUTION_SERVER_URL", "")  # For global WebSocket mode
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")  # Global API key for WebSocket auth

# Message Delay Configuration (to avoid WhatsApp bans)
# Adds human-like delays before sending messages
MESSAGE_DELAY_ENABLED = os.getenv("MESSAGE_DELAY_ENABLED", "true").lower() == "true"
MESSAGE_DELAY_MIN_MS = int(os.getenv("MESSAGE_DELAY_MIN_MS", "1000"))  # Minimum delay in ms
MESSAGE_DELAY_MAX_MS = int(os.getenv("MESSAGE_DELAY_MAX_MS", "3000"))  # Maximum delay in ms
TYPING_INDICATOR_ENABLED = os.getenv("TYPING_INDICATOR_ENABLED", "true").lower() == "true"
