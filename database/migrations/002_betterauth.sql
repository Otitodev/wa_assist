-- BetterAuth Migration
-- Run this in the Supabase SQL editor after 001_add_auth_tables.sql

-- BetterAuth core tables
CREATE TABLE IF NOT EXISTS "user" (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  email         TEXT UNIQUE NOT NULL,
  "emailVerified" BOOLEAN DEFAULT FALSE,
  image         TEXT,
  display_name  TEXT,
  "createdAt"   TIMESTAMPTZ DEFAULT NOW(),
  "updatedAt"   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS session (
  id           TEXT PRIMARY KEY,
  "userId"     TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  token        TEXT UNIQUE NOT NULL,
  "expiresAt"  TIMESTAMPTZ NOT NULL,
  "ipAddress"  TEXT,
  "userAgent"  TEXT,
  "createdAt"  TIMESTAMPTZ DEFAULT NOW(),
  "updatedAt"  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS account (
  id             TEXT PRIMARY KEY,
  "userId"       TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  "accountId"    TEXT NOT NULL,
  "providerId"   TEXT NOT NULL,
  "accessToken"  TEXT,
  "refreshToken" TEXT,
  "expiresAt"    TIMESTAMPTZ,
  password       TEXT,
  "createdAt"    TIMESTAMPTZ DEFAULT NOW(),
  "updatedAt"    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS verification (
  id           TEXT PRIMARY KEY,
  identifier   TEXT NOT NULL,
  value        TEXT NOT NULL,
  "expiresAt"  TIMESTAMPTZ NOT NULL,
  "createdAt"  TIMESTAMPTZ DEFAULT NOW(),
  "updatedAt"  TIMESTAMPTZ DEFAULT NOW()
);

-- Required by the JWT plugin (stores JWKS key pairs)
CREATE TABLE IF NOT EXISTS jwks (
  id           TEXT PRIMARY KEY,
  "publicKey"  TEXT NOT NULL,
  "privateKey" TEXT NOT NULL,
  "createdAt"  TIMESTAMPTZ NOT NULL
);

-- Re-point user_tenants and tenants → new BetterAuth "user" table
-- Must clear stale Supabase Auth IDs before adding FK (new "user" table is empty)

ALTER TABLE user_tenants DROP CONSTRAINT IF EXISTS user_tenants_user_id_fkey;
ALTER TABLE tenants DROP CONSTRAINT IF EXISTS tenants_owner_user_id_fkey;

-- Wipe rows referencing old Supabase Auth UUIDs (they won't exist in BetterAuth's user table)
TRUNCATE TABLE user_tenants;
UPDATE tenants SET owner_user_id = NULL;

ALTER TABLE user_tenants ALTER COLUMN user_id TYPE TEXT USING user_id::TEXT;
ALTER TABLE tenants ALTER COLUMN owner_user_id TYPE TEXT USING owner_user_id::TEXT;

ALTER TABLE user_tenants ADD CONSTRAINT user_tenants_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE CASCADE;

ALTER TABLE tenants ADD CONSTRAINT tenants_owner_user_id_fkey
  FOREIGN KEY (owner_user_id) REFERENCES "user"(id) ON DELETE SET NULL;

-- Remove old Supabase-auth-backed users table (only after data migrated)
-- DROP TABLE IF EXISTS users;
