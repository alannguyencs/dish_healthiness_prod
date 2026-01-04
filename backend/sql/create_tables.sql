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
