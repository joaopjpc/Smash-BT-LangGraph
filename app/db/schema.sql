-- Schema inicial do projeto
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS customer (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    channel text NOT NULL,
    channel_user_id text NOT NULL,
    name text NULL,
    phone text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT customer_channel_user_id_uniq UNIQUE (channel, channel_user_id)
);

CREATE TABLE IF NOT EXISTS message (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id uuid NOT NULL REFERENCES customer(id) ON DELETE CASCADE,
    direction text NOT NULL,
    text text NOT NULL,
    provider_message_id text NULL,
    raw_payload jsonb NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT message_customer_provider_uniq UNIQUE (customer_id, provider_message_id)
);

CREATE INDEX IF NOT EXISTS idx_message_customer_created_at
    ON message (customer_id, created_at DESC);

CREATE TABLE IF NOT EXISTS trial_class_booking (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id uuid NOT NULL REFERENCES customer(id) ON DELETE CASCADE,
    desired_datetime timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'pending',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trial_booking_customer_created_at
    ON trial_class_booking (customer_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_trial_booking_desired_datetime
    ON trial_class_booking (desired_datetime);

CREATE UNIQUE INDEX IF NOT EXISTS uq_trial_booking_customer_desired_datetime
    ON trial_class_booking (customer_id, desired_datetime);
