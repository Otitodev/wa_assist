-- ============================================================================
-- Migration 003: Billing Tables
-- Run this in Supabase SQL Editor if you already have the base schema set up.
-- Safe to run multiple times (uses IF NOT EXISTS / ON CONFLICT DO NOTHING).
-- ============================================================================

-- Plans catalog
CREATE TABLE IF NOT EXISTS plans (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,                  -- 'free', 'starter', 'growth', 'agency'
    display_name TEXT NOT NULL,
    price_usd NUMERIC(10,2) DEFAULT 0,
    price_ngn NUMERIC(12,2) DEFAULT 0,
    price_usd_annual NUMERIC(10,2) DEFAULT 0,   -- annual price per month (20% off)
    price_ngn_annual NUMERIC(12,2) DEFAULT 0,
    max_instances INT DEFAULT 1,
    max_conversations_per_month INT DEFAULT 100, -- -1 = unlimited
    features JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE plans IS 'Subscription plan catalog';
COMMENT ON COLUMN plans.max_conversations_per_month IS '-1 means unlimited';

-- Seed the 4 default plans (idempotent)
INSERT INTO plans (name, display_name, price_usd, price_ngn, price_usd_annual, price_ngn_annual, max_instances, max_conversations_per_month, features)
VALUES
    ('free',    'Free',    0,   0,       0,      0,      1,  100,   '{"typing_indicator": false, "media_processing": false, "context_memory": false, "analytics": false}'),
    ('starter', 'Starter', 29,  15000,   23.20,  12000,  2,  1000,  '{"typing_indicator": true, "media_processing": false, "context_memory": true, "analytics": true}'),
    ('growth',  'Growth',  79,  45000,   63.20,  36000,  5,  5000,  '{"typing_indicator": true, "media_processing": true, "context_memory": true, "analytics": true}'),
    ('agency',  'Agency',  199, 120000,  159.20, 96000,  -1, 25000, '{"typing_indicator": true, "media_processing": true, "context_memory": true, "analytics": true, "white_label": true, "priority_support": true}')
ON CONFLICT (name) DO NOTHING;


-- Tenant subscriptions (one row per tenant)
CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    plan_id INTEGER NOT NULL REFERENCES plans(id),
    status TEXT DEFAULT 'active',                   -- active | paused | cancelled | past_due
    billing_cycle TEXT DEFAULT 'monthly',            -- monthly | annual
    currency TEXT DEFAULT 'USD',                     -- USD | NGN
    processor TEXT NOT NULL DEFAULT 'free',          -- free | paystack | lemonsqueezy | flutterwave
    processor_subscription_id TEXT UNIQUE,
    processor_customer_id TEXT,
    current_period_start TIMESTAMPTZ DEFAULT NOW(),
    current_period_end TIMESTAMPTZ DEFAULT NOW() + INTERVAL '1 month',
    cancel_at_period_end BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id)                                -- one active subscription per tenant
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_tenant ON subscriptions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_processor_id
    ON subscriptions(processor_subscription_id)
    WHERE processor_subscription_id IS NOT NULL;

COMMENT ON TABLE subscriptions IS 'Tenant subscription records';


-- Monthly AI conversation usage per tenant
CREATE TABLE IF NOT EXISTS usage_records (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    month DATE NOT NULL,            -- first day of the month, e.g. 2026-03-01
    ai_conversations INT DEFAULT 0,
    UNIQUE(tenant_id, month)
);

CREATE INDEX IF NOT EXISTS idx_usage_tenant_month ON usage_records(tenant_id, month);

COMMENT ON TABLE usage_records IS 'Monthly AI conversation usage per tenant';


-- Auto-create a free subscription whenever a new tenant is inserted
CREATE OR REPLACE FUNCTION init_free_subscription()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO subscriptions (tenant_id, plan_id, processor)
    SELECT NEW.id, p.id, 'free'
    FROM plans p
    WHERE p.name = 'free'
    ON CONFLICT (tenant_id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION init_free_subscription IS
    'Auto-creates a free subscription when a tenant is created';

-- Drop and re-create the trigger so this migration is idempotent
DROP TRIGGER IF EXISTS trg_init_free_subscription ON tenants;
CREATE TRIGGER trg_init_free_subscription
    AFTER INSERT ON tenants
    FOR EACH ROW EXECUTE FUNCTION init_free_subscription();


-- Back-fill: give every existing tenant without a subscription a free plan
INSERT INTO subscriptions (tenant_id, plan_id, processor)
SELECT t.id, p.id, 'free'
FROM tenants t
CROSS JOIN plans p
WHERE p.name = 'free'
  AND NOT EXISTS (
      SELECT 1 FROM subscriptions s WHERE s.tenant_id = t.id
  );
