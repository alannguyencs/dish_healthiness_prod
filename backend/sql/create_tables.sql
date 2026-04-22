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

-- Table: personalized_food_descriptions
-- Per-user food upload index. One row per DishImageQuery owned by a user,
-- keyed on query_id so later stages can join back to the dish record and
-- its result_gemini blob without duplicating JSON payloads here.
-- Stage 0 writes user_id, query_id, created_at, updated_at.
-- Stage 2 fills image_url, description, tokens, similarity_score_on_insert.
-- Stage 4 fills confirmed_dish_name, confirmed_portions, confirmed_tokens.
-- Stage 8 fills corrected_nutrition_data.
CREATE TABLE IF NOT EXISTS personalized_food_descriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    query_id INTEGER NOT NULL REFERENCES dish_image_query_prod_dev(id) ON DELETE CASCADE,
    image_url VARCHAR,
    description TEXT,
    tokens JSONB,
    similarity_score_on_insert FLOAT,
    confirmed_dish_name TEXT,
    confirmed_portions FLOAT,
    confirmed_tokens JSONB,
    corrected_nutrition_data JSONB,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

-- Lookup by owner (Stage 2 / Stage 6 primary access path)
CREATE INDEX IF NOT EXISTS idx_personalized_food_descriptions_user_id
    ON personalized_food_descriptions(user_id);

-- Lookup by dish query (Stage 4 / Stage 8 update path)
-- Also enforces 1:1 with dish_image_query_prod_dev
CREATE UNIQUE INDEX IF NOT EXISTS uq_personalized_food_descriptions_query_id
    ON personalized_food_descriptions(query_id);

-- Table: nutrition_foods
-- Unified row table for the four source nutrition databases (Malaysian
-- food calories, MyFCD, Anuvaad INDB 2024, CIQUAL 2020). One row per
-- food item across all sources. Direct columns for the four macros plus
-- standard serving fields. raw_data JSONB stores source-specific extras
-- (full Anuvaad nutrient set, CIQUAL micros, Malaysian portion text)
-- so Stage 7 can read either the direct columns or the JSON blob.
-- searchable_document is precomputed at seed time (variations and
-- synonyms expanded once) so the runtime BM25 index build is a simple
-- whitespace split.
CREATE TABLE IF NOT EXISTS nutrition_foods (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_food_id TEXT NOT NULL,
    food_name TEXT NOT NULL,
    food_name_eng TEXT,
    category TEXT,
    searchable_document TEXT NOT NULL,
    calories FLOAT,
    carbs_g FLOAT,
    protein_g FLOAT,
    fat_g FLOAT,
    fiber_g FLOAT,
    serving_size_grams FLOAT,
    serving_unit TEXT,
    raw_data JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

-- Source filter (service partitions the corpus by source before BM25)
CREATE INDEX IF NOT EXISTS idx_nutrition_foods_source
    ON nutrition_foods(source);

-- Idempotent upsert key for the seed script
CREATE UNIQUE INDEX IF NOT EXISTS uq_nutrition_foods_source_food_id
    ON nutrition_foods(source, source_food_id);

-- Table: nutrition_myfcd_nutrients
-- Long-format MyFCD nutrient detail. Joined back to the parent
-- nutrition_foods row by (source='myfcd', source_food_id=ndb_id) so the
-- service can reconstruct the nested .nutrients dict that downstream
-- consumers expect. Soft join (no DB-level FK) because the nutrient
-- table only carries values for MyFCD rows.
CREATE TABLE IF NOT EXISTS nutrition_myfcd_nutrients (
    id SERIAL PRIMARY KEY,
    ndb_id TEXT NOT NULL,
    nutrient_name TEXT NOT NULL,
    value_per_100g FLOAT,
    value_per_serving FLOAT,
    unit TEXT,
    category TEXT
);

-- Lookup by parent food (service load path)
CREATE INDEX IF NOT EXISTS idx_nutrition_myfcd_nutrients_ndb_id
    ON nutrition_myfcd_nutrients(ndb_id);

-- Idempotent upsert key for the seed script
CREATE UNIQUE INDEX IF NOT EXISTS uq_nutrition_myfcd_nutrients_ndb_nutrient
    ON nutrition_myfcd_nutrients(ndb_id, nutrient_name);
