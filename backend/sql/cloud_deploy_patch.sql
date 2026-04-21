-- Idempotent patches to align cloud schema with local delta where the
-- dish_healthiness app and related services expect parity.
-- Run after create_tables.sql (nutrition / personalized / dish indexes).

-- conversation_message: columns used for recommendation linkage.
ALTER TABLE conversation_message
    ADD COLUMN IF NOT EXISTS personalized_domain VARCHAR;

ALTER TABLE conversation_message
    ADD COLUMN IF NOT EXISTS recommendation_id INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'conversation_message_recommendation_id_fkey'
    ) THEN
        ALTER TABLE conversation_message
            ADD CONSTRAINT conversation_message_recommendation_id_fkey
            FOREIGN KEY (recommendation_id) REFERENCES recommendation (id);
    END IF;
END $$;

-- Coach: template coach toggle (local parity).
ALTER TABLE coach_proactive_reminder_settings_2601
    ADD COLUMN IF NOT EXISTS template_coach_enabled BOOLEAN NOT NULL DEFAULT true;

-- Indexes present on local public.users / detalytics_conversation.
CREATE INDEX IF NOT EXISTS ix_users_id ON public.users (id);

CREATE INDEX IF NOT EXISTS ix_detalytics_conversation_id
    ON public.detalytics_conversation (id);
