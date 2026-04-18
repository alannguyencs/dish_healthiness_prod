-- Create tables for dish_healthiness application
-- Excludes: users table (managed separately)

-- Table: dish_image_query_prod_dev
-- Stores user-submitted food images and AI analysis results
CREATE TABLE IF NOT EXISTS dish_image_query_prod_dev (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    image_url VARCHAR,
    result_openai JSONB,
    result_gemini JSONB,
    dish_position INTEGER,
    created_at TIMESTAMP NOT NULL,
    target_date TIMESTAMP
);

-- Create index on id for faster lookups
CREATE INDEX IF NOT EXISTS idx_dish_image_query_prod_dev_id ON dish_image_query_prod_dev(id);

-- Create index on user_id for faster user-based queries
CREATE INDEX IF NOT EXISTS idx_dish_image_query_prod_dev_user_id ON dish_image_query_prod_dev(user_id);

-- One row per (user, day, slot). Re-uploading a slot now REPLACES the prior row
-- via replace_slot_atomic; this partial unique index is the DB-level guard
-- against concurrent upload races slipping past the application transaction.
CREATE UNIQUE INDEX IF NOT EXISTS uq_dish_image_query_prod_dev_user_target_position
    ON dish_image_query_prod_dev (user_id, (target_date::date), dish_position)
    WHERE target_date IS NOT NULL AND dish_position IS NOT NULL;

-- MAX_DISHES_PER_DATE is enforced at the API layer (date.py) but a non-browser
-- client could otherwise insert dish_position=99. Pair this with the unique
-- index above to cap rows-per-day at 5 at the DB layer too.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_dish_image_query_prod_dev_dish_position_range'
    ) THEN
        ALTER TABLE dish_image_query_prod_dev
            ADD CONSTRAINT ck_dish_image_query_prod_dev_dish_position_range
            CHECK (dish_position IS NULL OR (dish_position BETWEEN 1 AND 5));
    END IF;
END $$;
