-- Migration: Add authentication tables
-- Created: 2026-01-27
-- Description: Adds users and user_tenants tables for Supabase Auth integration

-- ============================================================================
-- USERS TABLE (extends Supabase auth.users)
-- ============================================================================
-- Stores additional user profile data beyond Supabase Auth
-- Links to auth.users via auth_user_id (UUID from Supabase Auth)

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id UUID UNIQUE NOT NULL,  -- References Supabase auth.users(id)
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_users_auth_user_id ON users(auth_user_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

COMMENT ON TABLE users IS 'User profiles extending Supabase Auth';
COMMENT ON COLUMN users.auth_user_id IS 'UUID from Supabase auth.users table';


-- ============================================================================
-- USER_TENANTS TABLE (User-Tenant Relationship / Access Control)
-- ============================================================================
-- Many-to-many: users can access multiple tenants, tenants can have multiple users
-- Role hierarchy: owner > admin > member

CREATE TABLE IF NOT EXISTS user_tenants (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL DEFAULT 'member',  -- 'owner', 'admin', 'member'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, tenant_id)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_user_tenants_user ON user_tenants(user_id);
CREATE INDEX IF NOT EXISTS idx_user_tenants_tenant ON user_tenants(tenant_id);
CREATE INDEX IF NOT EXISTS idx_user_tenants_role ON user_tenants(role);

COMMENT ON TABLE user_tenants IS 'User access to tenants with roles';
COMMENT ON COLUMN user_tenants.role IS 'User role: owner (full control), admin (manage), member (view/operate)';


-- ============================================================================
-- TENANT TABLE MODIFICATION
-- ============================================================================
-- Add owner reference to tenants table

ALTER TABLE tenants
ADD COLUMN IF NOT EXISTS owner_user_id UUID REFERENCES users(id);

CREATE INDEX IF NOT EXISTS idx_tenants_owner ON tenants(owner_user_id);

COMMENT ON COLUMN tenants.owner_user_id IS 'Primary owner of this tenant';


-- ============================================================================
-- ROLE DEFINITIONS (for reference)
-- ============================================================================
--
-- | Role   | Permissions                                    |
-- |--------|------------------------------------------------|
-- | owner  | Full control: delete tenant, transfer ownership|
-- | admin  | Manage: edit settings, invite/remove users     |
-- | member | Operate: view sessions, pause/resume           |
--
