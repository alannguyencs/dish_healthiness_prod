-- One-time cleanup for the "Personalized Data (Research only)" card feature.
-- Wipes every pre-feature dish upload + personalization row so no row exists
-- without the new result_gemini.flash_caption key. See
-- docs/plan/260419_personalized_data_card.md for the rationale.
--
-- NOT a migration file: DML (DELETE) is stripped by scripts/run_migrations.py.
-- Operator runs this manually via psql once, before or immediately after
-- deploying the feature code.
--
-- Run with:
--   psql -h $DB_URL -U $DB_USERNAME -d $DB_NAME \
--        -f scripts/cleanup/260419_personalized_data_card_purge.sql

BEGIN;

DELETE FROM personalized_food_descriptions;
DELETE FROM dish_image_query_prod_dev;

COMMIT;
