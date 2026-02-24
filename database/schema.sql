-- Whaply Database Schema
-- Run this in Supabase SQL Editor to create all required tables

-- ============================================================================
-- TENANTS TABLE
-- ============================================================================
-- Stores tenant/instance configuration
-- Each tenant represents a WhatsApp instance with its own Evolution API config

CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    instance_name VARCHAR(255) UNIQUE NOT NULL,
    evo_server_url VARCHAR(500) NOT NULL,
    evo_api_key VARCHAR(500),
    system_prompt TEXT,
    llm_provider VARCHAR(50) DEFAULT 'anthropic',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenants_instance_name ON tenants(instance_name);

COMMENT ON TABLE tenants IS 'WhatsApp instances and their configuration';
COMMENT ON COLUMN tenants.instance_name IS 'Unique instance identifier from Evolution API';
COMMENT ON COLUMN tenants.evo_server_url IS 'Evolution API server URL';
COMMENT ON COLUMN tenants.evo_api_key IS 'Evolution API key for authentication';
COMMENT ON COLUMN tenants.system_prompt IS 'Custom AI system prompt for this tenant';
COMMENT ON COLUMN tenants.llm_provider IS 'LLM provider to use (anthropic, openai, etc)';


-- ============================================================================
-- SESSIONS TABLE
-- ============================================================================
-- Tracks conversation state and pause/resume status

CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    chat_id VARCHAR(255) NOT NULL,
    is_paused BOOLEAN DEFAULT FALSE,
    pause_reason VARCHAR(100),
    last_message_at TIMESTAMPTZ,
    last_human_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, chat_id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_tenant_chat ON sessions(tenant_id, chat_id);
CREATE INDEX IF NOT EXISTS idx_sessions_paused_last_human ON sessions(is_paused, last_human_at)
    WHERE is_paused = true;

COMMENT ON TABLE sessions IS 'Conversation sessions with pause/resume state';
COMMENT ON COLUMN sessions.chat_id IS 'WhatsApp chat ID (e.g., 5511999999999@s.whatsapp.net)';
COMMENT ON COLUMN sessions.is_paused IS 'True when human has taken over conversation';
COMMENT ON COLUMN sessions.pause_reason IS 'Reason for pause (e.g., human_takeover, manual_pause)';
COMMENT ON COLUMN sessions.last_message_at IS 'Timestamp of last message in this session';
COMMENT ON COLUMN sessions.last_human_at IS 'Timestamp when business owner last sent a message';


-- ============================================================================
-- MESSAGES TABLE
-- ============================================================================
-- Stores all inbound and outbound messages

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    chat_id VARCHAR(255) NOT NULL,
    message_id VARCHAR(255) NOT NULL,
    from_me BOOLEAN DEFAULT FALSE,
    message_type VARCHAR(50),
    text TEXT,
    raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_tenant_msg ON messages(tenant_id, message_id);
CREATE INDEX IF NOT EXISTS idx_messages_chat_created ON messages(chat_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_tenant_chat ON messages(tenant_id, chat_id);

COMMENT ON TABLE messages IS 'All WhatsApp messages (inbound and outbound)';
COMMENT ON COLUMN messages.message_id IS 'Unique message ID from Evolution API';
COMMENT ON COLUMN messages.from_me IS 'True if message was sent by business owner or AI';
COMMENT ON COLUMN messages.message_type IS 'Message type from Evolution API (conversation, image, etc)';
COMMENT ON COLUMN messages.text IS 'Extracted text content';
COMMENT ON COLUMN messages.raw IS 'Full raw payload from Evolution API for debugging';


-- ============================================================================
-- PROCESSED_EVENTS TABLE (Idempotency Tracking)
-- ============================================================================
-- Tracks processed webhook events to prevent duplicate processing

CREATE TABLE IF NOT EXISTS processed_events (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    message_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    action_taken VARCHAR(100),
    processed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, message_id, event_type)
);

CREATE INDEX IF NOT EXISTS idx_processed_events_tenant_msg ON processed_events(tenant_id, message_id);
CREATE INDEX IF NOT EXISTS idx_processed_events_processed_at ON processed_events(processed_at);

COMMENT ON TABLE processed_events IS 'Tracks processed webhook events for idempotency';
COMMENT ON COLUMN processed_events.message_id IS 'Message ID from webhook';
COMMENT ON COLUMN processed_events.event_type IS 'Event type (e.g., messages.upsert)';
COMMENT ON COLUMN processed_events.action_taken IS 'Action taken (paused, ai_replied, ignored_paused, etc)';
COMMENT ON COLUMN processed_events.processed_at IS 'When this event was processed (for cleanup)';


-- ============================================================================
-- SAMPLE DATA (Optional - for testing)
-- ============================================================================
-- Uncomment to insert sample tenant data

-- INSERT INTO tenants (instance_name, evo_server_url, system_prompt, llm_provider)
-- VALUES (
--     'demo-instance',
--     'https://your-evolution-server.com',
--     'You are a helpful WhatsApp assistant for Demo Company. Be professional and friendly.',
--     'anthropic'
-- );


-- ============================================================================
-- CLEANUP FUNCTION (Optional)
-- ============================================================================
-- Function to clean up old processed_events (can be called from cron)

CREATE OR REPLACE FUNCTION cleanup_old_processed_events(days_to_keep INTEGER DEFAULT 7)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM processed_events
    WHERE processed_at < NOW() - (days_to_keep || ' days')::INTERVAL;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_processed_events IS 'Delete processed_events older than specified days';

-- Example usage:
-- SELECT cleanup_old_processed_events(7); -- Delete events older than 7 days


-- ============================================================================
-- AUTO-RESUME FUNCTION (Optional)
-- ============================================================================
-- Function to auto-resume paused sessions after inactivity

CREATE OR REPLACE FUNCTION auto_resume_paused_sessions(hours_inactive INTEGER DEFAULT 2)
RETURNS INTEGER AS $$
DECLARE
    resumed_count INTEGER;
BEGIN
    UPDATE sessions
    SET
        is_paused = FALSE,
        pause_reason = NULL,
        updated_at = NOW()
    WHERE
        is_paused = TRUE
        AND last_human_at < NOW() - (hours_inactive || ' hours')::INTERVAL;

    GET DIAGNOSTICS resumed_count = ROW_COUNT;
    RETURN resumed_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION auto_resume_paused_sessions IS 'Auto-resume sessions paused for more than specified hours';

-- Example usage:
-- SELECT auto_resume_paused_sessions(2); -- Resume sessions idle for > 2 hours
