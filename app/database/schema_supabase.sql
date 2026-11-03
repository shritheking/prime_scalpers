-- ====================================================================
-- PRIME SCALPERS • SUPABASE POSTGRESQL SCHEMA MIGRATION
-- Run this script in your Supabase SQL Editor
-- ====================================================================

-- 1. Create Enums
DO $$ BEGIN
    CREATE TYPE verification_status_enum AS ENUM (
        'PENDING', 'MANUAL_REVIEW', 'VERIFIED', 'WRONG_AFFILIATE', 
        'DEPOSIT_REQUIRED', 'NOT_FOUND', 'RETRY_PENDING', 'REJECTED'
    );
EXCEPTION WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE registration_status_enum AS ENUM (
        'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'INVITED', 'JOINED'
    );
EXCEPTION WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE challenge_status_enum AS ENUM (
        'DRAFT', 'OPEN', 'CLOSED', 'ARCHIVED'
    );
EXCEPTION WHEN duplicate_object THEN null;
END $$;

-- 2. Administrators Table
CREATE TABLE IF NOT EXISTS admins (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(100),
    full_name VARCHAR(150),
    is_super_admin BOOLEAN DEFAULT FALSE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_admins_telegram_id ON admins(telegram_id);

-- 3. Participants Table
CREATE TABLE IF NOT EXISTS participants (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(100),
    full_name VARCHAR(150) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_participants_telegram_id ON participants(telegram_id);

-- 4. Challenges Table
CREATE TABLE IF NOT EXISTS challenges (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    minimum_deposit DOUBLE PRECISION DEFAULT 100.0 NOT NULL,
    max_slots INTEGER DEFAULT 50 NOT NULL,
    allocated_slots INTEGER DEFAULT 0 NOT NULL,
    status challenge_status_enum DEFAULT 'OPEN'::challenge_status_enum NOT NULL,
    registration_deadline TIMESTAMP WITH TIME ZONE,
    affiliate_link_id VARCHAR(50) DEFAULT '2414647' NOT NULL,
    invite_expiry_hours INTEGER DEFAULT 24 NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 5. Registrations Table (with duplicate prevention constraint)
CREATE TABLE IF NOT EXISTS registrations (
    id SERIAL PRIMARY KEY,
    participant_id INTEGER REFERENCES participants(id) ON DELETE CASCADE NOT NULL,
    challenge_id INTEGER REFERENCES challenges(id) ON DELETE CASCADE NOT NULL,
    quotex_trader_id VARCHAR(50) NOT NULL,
    account_type VARCHAR(20) DEFAULT 'new' NOT NULL,
    status registration_status_enum DEFAULT 'SUBMITTED'::registration_status_enum NOT NULL,
    verification_status verification_status_enum DEFAULT 'PENDING'::verification_status_enum NOT NULL,
    slot_reserved BOOLEAN DEFAULT FALSE NOT NULL,
    admin_notes TEXT,
    retry_count INTEGER DEFAULT 0 NOT NULL,
    last_auto_checked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT uq_participant_challenge UNIQUE(participant_id, challenge_id)
);
CREATE INDEX IF NOT EXISTS idx_registrations_quotex_id ON registrations(quotex_trader_id);
CREATE INDEX IF NOT EXISTS idx_registrations_status ON registrations(status);
CREATE INDEX IF NOT EXISTS idx_registrations_verification ON registrations(verification_status);

-- 6. Verification Requests Table
CREATE TABLE IF NOT EXISTS verification_requests (
    id SERIAL PRIMARY KEY,
    registration_id INTEGER REFERENCES registrations(id) ON DELETE CASCADE NOT NULL,
    provider_name VARCHAR(50) DEFAULT 'mtproto' NOT NULL,
    status verification_status_enum DEFAULT 'PENDING'::verification_status_enum NOT NULL,
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_v_req_reg_id ON verification_requests(registration_id);

-- 7. Verification Results Table (Full Quotex Telemetry)
CREATE TABLE IF NOT EXISTS verification_results (
    id SERIAL PRIMARY KEY,
    request_id INTEGER REFERENCES verification_requests(id) ON DELETE CASCADE NOT NULL,
    registration_id INTEGER REFERENCES registrations(id) ON DELETE CASCADE NOT NULL,
    verified_by_admin_id BIGINT,
    trader_id VARCHAR(50) NOT NULL,
    affiliate_link_id VARCHAR(50),
    deposit_amount DOUBLE PRECISION,
    balance DOUBLE PRECISION,
    deposits_count INTEGER,
    withdrawals_count INTEGER,
    withdrawals_sum DOUBLE PRECISION,
    country VARCHAR(100),
    registration_date VARCHAR(50),
    is_affiliate_matched BOOLEAN DEFAULT FALSE NOT NULL,
    is_deposit_sufficient BOOLEAN DEFAULT FALSE NOT NULL,
    raw_evidence TEXT,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_v_res_reg_id ON verification_results(registration_id);

-- 8. Single-Use Invite Links Table
CREATE TABLE IF NOT EXISTS invite_links (
    id SERIAL PRIMARY KEY,
    registration_id INTEGER REFERENCES registrations(id) ON DELETE CASCADE NOT NULL,
    participant_telegram_id BIGINT NOT NULL,
    invite_link VARCHAR(255) UNIQUE NOT NULL,
    member_limit INTEGER DEFAULT 1 NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE NOT NULL,
    is_used BOOLEAN DEFAULT FALSE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_invite_participant ON invite_links(participant_telegram_id);

-- 9. Channel Members Audit Table
CREATE TABLE IF NOT EXISTS channel_members (
    id SERIAL PRIMARY KEY,
    channel_id BIGINT NOT NULL,
    telegram_id BIGINT NOT NULL,
    registration_id INTEGER REFERENCES registrations(id) ON DELETE SET NULL,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    status VARCHAR(30) DEFAULT 'member' NOT NULL,
    is_authorized BOOLEAN DEFAULT FALSE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT uq_channel_telegram_user UNIQUE(channel_id, telegram_id)
);
CREATE INDEX IF NOT EXISTS idx_channel_members_user ON channel_members(telegram_id);

-- 10. Announcements Table
CREATE TABLE IF NOT EXISTS announcements (
    id SERIAL PRIMARY KEY,
    admin_telegram_id BIGINT NOT NULL,
    message_text TEXT NOT NULL,
    target_challenge_id INTEGER REFERENCES challenges(id) ON DELETE SET NULL,
    total_targets INTEGER DEFAULT 0 NOT NULL,
    success_count INTEGER DEFAULT 0 NOT NULL,
    fail_count INTEGER DEFAULT 0 NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 11. Audit Logs Table
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    admin_telegram_id BIGINT NOT NULL,
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(50),
    target_id VARCHAR(50),
    details TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);

-- 12. System Settings Table
CREATE TABLE IF NOT EXISTS system_settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT NOT NULL,
    description VARCHAR(255),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Seed Initial Challenges
INSERT INTO challenges (name, description, minimum_deposit, max_slots, status, affiliate_link_id, invite_expiry_hours)
VALUES 
    ('$100 Challenge', 'Introductory scalping challenge designed for high-discipline traders.', 100.0, 50, 'OPEN', '2414647', 24),
    ('$500 Challenge', 'Intermediate scalping tier with premium community access.', 500.0, 25, 'OPEN', '2414647', 24),
    ('$1,000 Challenge', 'Elite high-frequency scalpers group with priority analysis.', 1000.0, 10, 'OPEN', '2414647', 24)
ON CONFLICT DO NOTHING;

-- Seed Admin
INSERT INTO admins (telegram_id, username, full_name, is_super_admin, is_active)
VALUES (5188160752, 'PrimaryAdmin', 'Prime Scalpers Admin', true, true)
ON CONFLICT (telegram_id) DO NOTHING;
