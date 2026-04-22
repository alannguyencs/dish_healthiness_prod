-- =============================================================================
-- Migration: 260422_rename_corrected_nutrition_column.sql
-- Plan reference: docs/issues/260422.md — Tier 2, T2.8
--
-- Two coupled rewrites:
--
-- 1. SQL column rename on `personalized_food_descriptions`:
--        corrected_step2_data  ->  corrected_nutrition_data
--
-- 2. JSONB key renames inside `dish_image_query.result_gemini`:
--
--    Inside result_gemini.personalized_matches[*]:
--        prior_step2_data       ->  prior_nutrition_data
--        corrected_step2_data   ->  corrected_nutrition_data
--
--    Inside result_gemini.reference_image:
--        prior_step1_data       ->  prior_identification_data
--
-- The JSONB keys are echoed from the SQL column name and from the
-- reference_image payload into the Phase 2.3 Gemini prompt, so the
-- column rename and the JSONB rewrites must ship together.
--
-- IDEMPOTENCY: both halves are guarded.
--   - The ALTER TABLE is wrapped in an information_schema existence check,
--     so running it twice is a no-op on the second run.
--   - Each JSONB rename is guarded on a `j ? 'old_key'` key-exists check,
--     and the outer UPDATE's WHERE restricts to rows still carrying any
--     old key — so a second run writes nothing.
--
-- ROLLBACK: see the commented `-- DOWN` section at the bottom of this file.
-- Matches the convention set by 260422_rename_step_keys.sql.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- Part 1 — rename the SQL column (idempotent)
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'personalized_food_descriptions'
          AND column_name  = 'corrected_step2_data'
    ) THEN
        ALTER TABLE public.personalized_food_descriptions
            RENAME COLUMN corrected_step2_data TO corrected_nutrition_data;
        RAISE NOTICE 'rename_corrected_nutrition_column: column renamed';
    ELSE
        RAISE NOTICE 'rename_corrected_nutrition_column: column already renamed (no-op)';
    END IF;
END
$$;


-- -----------------------------------------------------------------------------
-- Part 2 — rename JSONB keys inside dish_image_query.result_gemini
-- -----------------------------------------------------------------------------
--
-- Each rename step is individually guarded on a JSONB key-exists check
-- (`j ? 'old'`) so re-running the migration is a byte-identical no-op on
-- already-migrated rows.

CREATE OR REPLACE FUNCTION pg_temp.rename_key(
    j jsonb,
    old_key text,
    new_key text
) RETURNS jsonb AS $$
    SELECT CASE
        WHEN j IS NULL THEN j
        WHEN j ? old_key
            THEN (j - old_key) || jsonb_build_object(new_key, j -> old_key)
        ELSE j
    END;
$$ LANGUAGE sql IMMUTABLE;


-- Rename both personalized_matches[*] keys.
CREATE OR REPLACE FUNCTION pg_temp.rename_personalized_match(m jsonb) RETURNS jsonb AS $$
    SELECT pg_temp.rename_key(
               pg_temp.rename_key(m, 'prior_step2_data',     'prior_nutrition_data'),
           'corrected_step2_data', 'corrected_nutrition_data');
$$ LANGUAGE sql IMMUTABLE;


-- Rename the single reference_image key.
CREATE OR REPLACE FUNCTION pg_temp.rename_reference_image(r jsonb) RETURNS jsonb AS $$
    SELECT CASE
        WHEN r IS NULL THEN r
        WHEN jsonb_typeof(r) <> 'object' THEN r
        ELSE pg_temp.rename_key(r, 'prior_step1_data', 'prior_identification_data')
    END;
$$ LANGUAGE sql IMMUTABLE;


-- Rewrite a full result_gemini value: reference_image, then personalized_matches[*].
CREATE OR REPLACE FUNCTION pg_temp.rewrite_result_gemini(rg jsonb) RETURNS jsonb AS $$
    WITH
    ref_renamed(j) AS (
        SELECT CASE
            WHEN rg ? 'reference_image'
                 AND jsonb_typeof(rg -> 'reference_image') = 'object'
            THEN jsonb_set(
                rg,
                '{reference_image}',
                pg_temp.rename_reference_image(rg -> 'reference_image')
            )
            ELSE rg
        END
    ),
    matches_renamed(j) AS (
        SELECT CASE
            WHEN (SELECT j FROM ref_renamed) ? 'personalized_matches'
                 AND jsonb_typeof((SELECT j FROM ref_renamed) -> 'personalized_matches') = 'array'
            THEN jsonb_set(
                (SELECT j FROM ref_renamed),
                '{personalized_matches}',
                COALESCE(
                    (
                        SELECT jsonb_agg(pg_temp.rename_personalized_match(elem))
                        FROM jsonb_array_elements((SELECT j FROM ref_renamed) -> 'personalized_matches') AS elem
                    ),
                    '[]'::jsonb
                )
            )
            ELSE (SELECT j FROM ref_renamed)
        END
    )
    SELECT j FROM matches_renamed;
$$ LANGUAGE sql IMMUTABLE;


-- Final UPDATE — idempotent because rewrite_result_gemini is a no-op when no
-- old keys are present. The WHERE clause restricts to rows still carrying at
-- least one old key so untouched rows are not rewritten (saves WAL churn on
-- re-runs).
UPDATE public.dish_image_query
SET result_gemini = pg_temp.rewrite_result_gemini(result_gemini)
WHERE result_gemini IS NOT NULL
  AND (
        -- reference_image carries the old key
        (
            jsonb_typeof(result_gemini -> 'reference_image') = 'object'
            AND (result_gemini -> 'reference_image') ? 'prior_step1_data'
        )
        -- any personalized_matches[*] element carries an old key
     OR EXISTS (
            SELECT 1
            FROM jsonb_array_elements(
                CASE
                    WHEN jsonb_typeof(result_gemini -> 'personalized_matches') = 'array'
                    THEN result_gemini -> 'personalized_matches'
                    ELSE '[]'::jsonb
                END
            ) AS m
            WHERE m ? 'prior_step2_data'
               OR m ? 'corrected_step2_data'
        )
  );


-- -----------------------------------------------------------------------------
-- Smoke test — raises EXCEPTION if any old key/column survives.
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    col_hits      bigint;
    ref_hits      bigint;
    match_hits    bigint;
BEGIN
    SELECT COUNT(*) INTO col_hits
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'personalized_food_descriptions'
      AND column_name  = 'corrected_step2_data';

    SELECT COUNT(*) INTO ref_hits
    FROM public.dish_image_query
    WHERE jsonb_typeof(result_gemini -> 'reference_image') = 'object'
      AND (result_gemini -> 'reference_image') ? 'prior_step1_data';

    SELECT COUNT(*) INTO match_hits
    FROM public.dish_image_query, jsonb_array_elements(
        CASE WHEN jsonb_typeof(result_gemini -> 'personalized_matches') = 'array'
             THEN result_gemini -> 'personalized_matches'
             ELSE '[]'::jsonb END
    ) AS m
    WHERE m ? 'prior_step2_data' OR m ? 'corrected_step2_data';

    RAISE NOTICE 'rename_corrected_nutrition_column: column-survivors=%, reference_image-survivors=%, personalized_matches-survivors=%',
                 col_hits, ref_hits, match_hits;

    IF col_hits <> 0 OR ref_hits <> 0 OR match_hits <> 0 THEN
        RAISE EXCEPTION 'rename_corrected_nutrition_column: legacy names still present after forward migration (column=%, reference_image=%, matches=%)',
                        col_hits, ref_hits, match_hits;
    END IF;
END
$$;


COMMIT;

-- -----------------------------------------------------------------------------
-- Verification queries (run manually after the COMMIT above):
--
--   SELECT column_name FROM information_schema.columns
--   WHERE table_schema = 'public'
--     AND table_name   = 'personalized_food_descriptions'
--     AND column_name IN ('corrected_step2_data', 'corrected_nutrition_data');
--   Expected: only `corrected_nutrition_data`.
--
--   SELECT COUNT(*) FROM public.dish_image_query
--   WHERE jsonb_typeof(result_gemini -> 'reference_image') = 'object'
--     AND (result_gemini -> 'reference_image') ? 'prior_step1_data';
--   Expected: 0.
--
--   SELECT COUNT(*) FROM public.dish_image_query, jsonb_array_elements(
--       CASE WHEN jsonb_typeof(result_gemini -> 'personalized_matches') = 'array'
--            THEN result_gemini -> 'personalized_matches'
--            ELSE '[]'::jsonb END
--   ) AS m
--   WHERE m ? 'prior_step2_data' OR m ? 'corrected_step2_data';
--   Expected: 0.
-- -----------------------------------------------------------------------------


-- =============================================================================
-- DOWN (rollback)
--
-- The block below is commented out. To roll back, copy the block into a psql
-- session (or uncomment and re-run this file). It reverses every rename by
-- applying the same helper strategy with the key/column pairs swapped.
--
-- IMPORTANT: only run the rollback if the forward migration has been applied
-- and no new code has yet written the new names with semantically different
-- meanings. Since Tier 2 is a coupled deploy, a rollback should be paired with
-- redeploying the prior backend + frontend bundle.
-- =============================================================================
--
-- BEGIN;
--
-- DO $$
-- BEGIN
--     IF EXISTS (
--         SELECT 1
--         FROM information_schema.columns
--         WHERE table_schema = 'public'
--           AND table_name   = 'personalized_food_descriptions'
--           AND column_name  = 'corrected_nutrition_data'
--     ) THEN
--         ALTER TABLE public.personalized_food_descriptions
--             RENAME COLUMN corrected_nutrition_data TO corrected_step2_data;
--     END IF;
-- END
-- $$;
--
-- CREATE OR REPLACE FUNCTION pg_temp.rename_key(
--     j jsonb,
--     old_key text,
--     new_key text
-- ) RETURNS jsonb AS $fn$
--     SELECT CASE
--         WHEN j IS NULL THEN j
--         WHEN j ? old_key
--             THEN (j - old_key) || jsonb_build_object(new_key, j -> old_key)
--         ELSE j
--     END;
-- $fn$ LANGUAGE sql IMMUTABLE;
--
-- CREATE OR REPLACE FUNCTION pg_temp.rollback_personalized_match(m jsonb) RETURNS jsonb AS $fn$
--     SELECT pg_temp.rename_key(
--                pg_temp.rename_key(m, 'prior_nutrition_data',     'prior_step2_data'),
--            'corrected_nutrition_data', 'corrected_step2_data');
-- $fn$ LANGUAGE sql IMMUTABLE;
--
-- CREATE OR REPLACE FUNCTION pg_temp.rollback_reference_image(r jsonb) RETURNS jsonb AS $fn$
--     SELECT CASE
--         WHEN r IS NULL THEN r
--         WHEN jsonb_typeof(r) <> 'object' THEN r
--         ELSE pg_temp.rename_key(r, 'prior_identification_data', 'prior_step1_data')
--     END;
-- $fn$ LANGUAGE sql IMMUTABLE;
--
-- CREATE OR REPLACE FUNCTION pg_temp.rollback_result_gemini(rg jsonb) RETURNS jsonb AS $fn$
--     WITH
--     ref_renamed(j) AS (
--         SELECT CASE
--             WHEN rg ? 'reference_image'
--                  AND jsonb_typeof(rg -> 'reference_image') = 'object'
--             THEN jsonb_set(
--                 rg,
--                 '{reference_image}',
--                 pg_temp.rollback_reference_image(rg -> 'reference_image')
--             )
--             ELSE rg
--         END
--     ),
--     matches_renamed(j) AS (
--         SELECT CASE
--             WHEN (SELECT j FROM ref_renamed) ? 'personalized_matches'
--                  AND jsonb_typeof((SELECT j FROM ref_renamed) -> 'personalized_matches') = 'array'
--             THEN jsonb_set(
--                 (SELECT j FROM ref_renamed),
--                 '{personalized_matches}',
--                 COALESCE(
--                     (
--                         SELECT jsonb_agg(pg_temp.rollback_personalized_match(elem))
--                         FROM jsonb_array_elements((SELECT j FROM ref_renamed) -> 'personalized_matches') AS elem
--                     ),
--                     '[]'::jsonb
--                 )
--             )
--             ELSE (SELECT j FROM ref_renamed)
--         END
--     )
--     SELECT j FROM matches_renamed;
-- $fn$ LANGUAGE sql IMMUTABLE;
--
-- UPDATE public.dish_image_query
-- SET result_gemini = pg_temp.rollback_result_gemini(result_gemini)
-- WHERE result_gemini IS NOT NULL
--   AND (
--         (
--             jsonb_typeof(result_gemini -> 'reference_image') = 'object'
--             AND (result_gemini -> 'reference_image') ? 'prior_identification_data'
--         )
--      OR EXISTS (
--             SELECT 1
--             FROM jsonb_array_elements(
--                 CASE
--                     WHEN jsonb_typeof(result_gemini -> 'personalized_matches') = 'array'
--                     THEN result_gemini -> 'personalized_matches'
--                     ELSE '[]'::jsonb
--                 END
--             ) AS m
--             WHERE m ? 'prior_nutrition_data'
--                OR m ? 'corrected_nutrition_data'
--         )
--   );
--
-- COMMIT;
--
-- =============================================================================
-- End of migration 260422_rename_corrected_nutrition_column.sql
-- =============================================================================
