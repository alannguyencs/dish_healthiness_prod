-- =============================================================================
-- Migration: 260422_rename_step_keys.sql
-- Plan reference: docs/issues/260422.md — Tier 2, T2.2
--
-- Rewrites every row of public.dish_image_query.result_gemini in place,
-- replacing the legacy `step` / `step1_*` / `step2_*` JSONB keys with the
-- new `phase` / `identification_*` / `nutrition_*` key names.
--
-- Top-level result_gemini key map:
--     step                 -> phase
--     step1_data           -> identification_data
--     step1_confirmed      -> identification_confirmed
--     step1_error          -> identification_error
--     step2_data           -> nutrition_data
--     step2_corrected      -> nutrition_corrected
--     step2_error          -> nutrition_error
--
-- Per-iteration keys (inside result_gemini.iterations[*]):
--     step                 -> phase
--     step1_data           -> identification_data
--     step2_data           -> nutrition_data
--
-- Two iteration shapes exist in production data (see T2.1 audit):
--     1. FLAT           — iteration object carries step / step1_data / step2_data
--                         directly at its top level.
--     2. ANALYSIS-wrap  — iteration object carries an `analysis` sub-object
--                         which in turn carries step / step1_data / step2_data.
--   The migration rewrites whichever shape it finds and leaves the other
--   alone on a per-iteration basis.
--
-- Inner keys of step1_error / step2_error (`error_type`, `message`,
-- `occurred_at`, `retry_count`) are generic and are intentionally left
-- untouched — only the outer key name changes.
--
-- IDEMPOTENCY GATE: each rename step is guarded by a `? 'old_key'` JSONB
-- key-exists check. On a row that has already been migrated, every guard
-- is false, so the row is written back byte-identical (the outer UPDATE
-- still no-ops because the WHERE clause below restricts to rows that still
-- carry at least one old key). Running this script twice in a row produces
-- zero additional changes on the second run.
--
-- ROLLBACK: see the `-- DOWN` section at the bottom of this file.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- Forward migration
-- -----------------------------------------------------------------------------
--
-- We use a single UPDATE that calls a helper function defined in the
-- session-local `pg_temp` schema (auto-dropped at session end). Each rename
-- step is individually guarded on a JSONB key-exists check (`j ? 'old'`) so
-- re-running the migration is a byte-identical no-op on already-migrated rows.

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


CREATE OR REPLACE FUNCTION pg_temp.rename_top_level(j jsonb) RETURNS jsonb AS $$
    SELECT pg_temp.rename_key(
               pg_temp.rename_key(
                   pg_temp.rename_key(
                       pg_temp.rename_key(
                           pg_temp.rename_key(
                               pg_temp.rename_key(
                                   pg_temp.rename_key(j, 'step',            'phase'),
                               'step1_data',       'identification_data'),
                           'step1_confirmed',  'identification_confirmed'),
                       'step1_error',      'identification_error'),
                   'step2_data',       'nutrition_data'),
               'step2_corrected',  'nutrition_corrected'),
           'step2_error',      'nutrition_error');
$$ LANGUAGE sql IMMUTABLE;


-- Rename keys inside one iteration object. Handles both shapes:
--   FLAT         — keys live at the top of the iteration object.
--   ANALYSIS-wrap — keys live inside iteration -> 'analysis'.
-- Keys applied at the iteration level: step, step1_data, step2_data
-- (per T2.1 audit — step1_confirmed / step2_corrected / step1_error /
-- step2_error do not appear at iteration scope).
CREATE OR REPLACE FUNCTION pg_temp.rename_iteration(it jsonb) RETURNS jsonb AS $$
    WITH
    -- FLAT shape rewrite: applied always; each call is a no-op if the key is absent.
    flat_renamed(j) AS (
        SELECT pg_temp.rename_key(
                   pg_temp.rename_key(
                       pg_temp.rename_key(it, 'step',       'phase'),
                   'step1_data', 'identification_data'),
               'step2_data', 'nutrition_data')
    ),
    -- ANALYSIS-wrap rewrite: if the iteration carries an `analysis` object,
    -- rename the same three keys inside it.
    analysis_renamed(j) AS (
        SELECT CASE
            WHEN (SELECT j FROM flat_renamed) ? 'analysis'
                 AND jsonb_typeof((SELECT j FROM flat_renamed) -> 'analysis') = 'object'
            THEN jsonb_set(
                (SELECT j FROM flat_renamed),
                '{analysis}',
                pg_temp.rename_key(
                    pg_temp.rename_key(
                        pg_temp.rename_key(
                            (SELECT j FROM flat_renamed) -> 'analysis',
                            'step', 'phase'),
                        'step1_data', 'identification_data'),
                    'step2_data', 'nutrition_data')
            )
            ELSE (SELECT j FROM flat_renamed)
        END
    )
    SELECT j FROM analysis_renamed;
$$ LANGUAGE sql IMMUTABLE;


-- Rewrite the full result_gemini value: top-level, then iterations[*] if present.
CREATE OR REPLACE FUNCTION pg_temp.rewrite_result_gemini(rg jsonb) RETURNS jsonb AS $$
    WITH
    top_renamed(j) AS (
        SELECT pg_temp.rename_top_level(rg)
    ),
    iter_renamed(j) AS (
        SELECT CASE
            WHEN (SELECT j FROM top_renamed) ? 'iterations'
                 AND jsonb_typeof((SELECT j FROM top_renamed) -> 'iterations') = 'array'
            THEN jsonb_set(
                (SELECT j FROM top_renamed),
                '{iterations}',
                COALESCE(
                    (
                        SELECT jsonb_agg(pg_temp.rename_iteration(elem))
                        FROM jsonb_array_elements((SELECT j FROM top_renamed) -> 'iterations') AS elem
                    ),
                    '[]'::jsonb
                )
            )
            ELSE (SELECT j FROM top_renamed)
        END
    )
    SELECT j FROM iter_renamed;
$$ LANGUAGE sql IMMUTABLE;


-- Final UPDATE — idempotent because rewrite_result_gemini is a no-op when no
-- old keys are present. We also restrict the WHERE clause so untouched rows
-- are not rewritten unnecessarily (saves WAL churn on re-runs).
UPDATE public.dish_image_query
SET result_gemini = pg_temp.rewrite_result_gemini(result_gemini)
WHERE result_gemini IS NOT NULL
  AND (
        -- top-level legacy keys
        result_gemini ? 'step'
     OR result_gemini ? 'step1_data'
     OR result_gemini ? 'step1_confirmed'
     OR result_gemini ? 'step1_error'
     OR result_gemini ? 'step2_data'
     OR result_gemini ? 'step2_corrected'
     OR result_gemini ? 'step2_error'
        -- any iteration carrying a legacy key (flat OR analysis-wrapped)
     OR EXISTS (
            SELECT 1
            FROM jsonb_array_elements(
                CASE
                    WHEN jsonb_typeof(result_gemini -> 'iterations') = 'array'
                    THEN result_gemini -> 'iterations'
                    ELSE '[]'::jsonb
                END
            ) AS it
            WHERE it ? 'step'
               OR it ? 'step1_data'
               OR it ? 'step2_data'
               OR (
                    jsonb_typeof(it -> 'analysis') = 'object'
                    AND (
                        (it -> 'analysis') ? 'step'
                     OR (it -> 'analysis') ? 'step1_data'
                     OR (it -> 'analysis') ? 'step2_data'
                    )
               )
        )
  );


-- -----------------------------------------------------------------------------
-- Optional smoke test — raises NOTICE with counts of rows still carrying any
-- legacy key. Expected: zero for every key after the UPDATE above succeeds.
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    top_hits      bigint;
    iter_flat     bigint;
    iter_wrapped  bigint;
BEGIN
    SELECT COUNT(*) INTO top_hits
    FROM public.dish_image_query
    WHERE result_gemini ? 'step'
       OR result_gemini ? 'step1_data'
       OR result_gemini ? 'step1_confirmed'
       OR result_gemini ? 'step1_error'
       OR result_gemini ? 'step2_data'
       OR result_gemini ? 'step2_corrected'
       OR result_gemini ? 'step2_error';

    SELECT COUNT(*) INTO iter_flat
    FROM public.dish_image_query, jsonb_array_elements(
        CASE WHEN jsonb_typeof(result_gemini -> 'iterations') = 'array'
             THEN result_gemini -> 'iterations'
             ELSE '[]'::jsonb END
    ) AS it
    WHERE it ? 'step' OR it ? 'step1_data' OR it ? 'step2_data';

    SELECT COUNT(*) INTO iter_wrapped
    FROM public.dish_image_query, jsonb_array_elements(
        CASE WHEN jsonb_typeof(result_gemini -> 'iterations') = 'array'
             THEN result_gemini -> 'iterations'
             ELSE '[]'::jsonb END
    ) AS it
    WHERE jsonb_typeof(it -> 'analysis') = 'object'
      AND ((it -> 'analysis') ? 'step'
        OR (it -> 'analysis') ? 'step1_data'
        OR (it -> 'analysis') ? 'step2_data');

    RAISE NOTICE 'rename_step_keys: top-level legacy hits=%, flat-iteration hits=%, analysis-wrapped iteration hits=%',
                 top_hits, iter_flat, iter_wrapped;

    IF top_hits <> 0 OR iter_flat <> 0 OR iter_wrapped <> 0 THEN
        RAISE EXCEPTION 'rename_step_keys: legacy keys still present after forward migration (top=%, flat=%, wrapped=%)',
                        top_hits, iter_flat, iter_wrapped;
    END IF;
END
$$;


COMMIT;

-- -----------------------------------------------------------------------------
-- Verification query (run manually after the COMMIT above):
--
--   SELECT COUNT(*) FROM public.dish_image_query
--   WHERE result_gemini ? 'step1_data'
--      OR result_gemini ? 'step2_data'
--      OR result_gemini ? 'step';
--
-- Expected: 0.
-- -----------------------------------------------------------------------------


-- =============================================================================
-- DOWN (rollback)
--
-- The block below is commented out. To roll back, copy the block into a psql
-- session (or uncomment and re-run this file). It reverses every rename by
-- applying the same helper strategy with the key pairs swapped.
--
-- IMPORTANT: only run the rollback if the forward migration has been applied
-- and no new code has yet written the new key names with semantically different
-- meanings. Since Tier 2 is a coupled deploy, a rollback should be paired with
-- redeploying the prior backend + frontend bundle.
-- =============================================================================
--
-- BEGIN;
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
-- CREATE OR REPLACE FUNCTION pg_temp.rollback_top_level(j jsonb) RETURNS jsonb AS $fn$
--     SELECT pg_temp.rename_key(
--                pg_temp.rename_key(
--                    pg_temp.rename_key(
--                        pg_temp.rename_key(
--                            pg_temp.rename_key(
--                                pg_temp.rename_key(
--                                    pg_temp.rename_key(j, 'phase',                    'step'),
--                                'identification_data',       'step1_data'),
--                            'identification_confirmed',  'step1_confirmed'),
--                        'identification_error',      'step1_error'),
--                    'nutrition_data',            'step2_data'),
--                'nutrition_corrected',       'step2_corrected'),
--            'nutrition_error',           'step2_error');
-- $fn$ LANGUAGE sql IMMUTABLE;
--
-- CREATE OR REPLACE FUNCTION pg_temp.rollback_iteration(it jsonb) RETURNS jsonb AS $fn$
--     WITH
--     flat_renamed(j) AS (
--         SELECT pg_temp.rename_key(
--                    pg_temp.rename_key(
--                        pg_temp.rename_key(it, 'phase',              'step'),
--                    'identification_data', 'step1_data'),
--                'nutrition_data',      'step2_data')
--     ),
--     analysis_renamed(j) AS (
--         SELECT CASE
--             WHEN (SELECT j FROM flat_renamed) ? 'analysis'
--                  AND jsonb_typeof((SELECT j FROM flat_renamed) -> 'analysis') = 'object'
--             THEN jsonb_set(
--                 (SELECT j FROM flat_renamed),
--                 '{analysis}',
--                 pg_temp.rename_key(
--                     pg_temp.rename_key(
--                         pg_temp.rename_key(
--                             (SELECT j FROM flat_renamed) -> 'analysis',
--                             'phase',              'step'),
--                         'identification_data', 'step1_data'),
--                     'nutrition_data',      'step2_data')
--             )
--             ELSE (SELECT j FROM flat_renamed)
--         END
--     )
--     SELECT j FROM analysis_renamed;
-- $fn$ LANGUAGE sql IMMUTABLE;
--
-- CREATE OR REPLACE FUNCTION pg_temp.rollback_result_gemini(rg jsonb) RETURNS jsonb AS $fn$
--     WITH
--     top_renamed(j) AS (
--         SELECT pg_temp.rollback_top_level(rg)
--     ),
--     iter_renamed(j) AS (
--         SELECT CASE
--             WHEN (SELECT j FROM top_renamed) ? 'iterations'
--                  AND jsonb_typeof((SELECT j FROM top_renamed) -> 'iterations') = 'array'
--             THEN jsonb_set(
--                 (SELECT j FROM top_renamed),
--                 '{iterations}',
--                 COALESCE(
--                     (
--                         SELECT jsonb_agg(pg_temp.rollback_iteration(elem))
--                         FROM jsonb_array_elements((SELECT j FROM top_renamed) -> 'iterations') AS elem
--                     ),
--                     '[]'::jsonb
--                 )
--             )
--             ELSE (SELECT j FROM top_renamed)
--         END
--     )
--     SELECT j FROM iter_renamed;
-- $fn$ LANGUAGE sql IMMUTABLE;
--
-- UPDATE public.dish_image_query
-- SET result_gemini = pg_temp.rollback_result_gemini(result_gemini)
-- WHERE result_gemini IS NOT NULL
--   AND (
--         result_gemini ? 'phase'
--      OR result_gemini ? 'identification_data'
--      OR result_gemini ? 'identification_confirmed'
--      OR result_gemini ? 'identification_error'
--      OR result_gemini ? 'nutrition_data'
--      OR result_gemini ? 'nutrition_corrected'
--      OR result_gemini ? 'nutrition_error'
--      OR EXISTS (
--             SELECT 1
--             FROM jsonb_array_elements(
--                 CASE
--                     WHEN jsonb_typeof(result_gemini -> 'iterations') = 'array'
--                     THEN result_gemini -> 'iterations'
--                     ELSE '[]'::jsonb
--                 END
--             ) AS it
--             WHERE it ? 'phase'
--                OR it ? 'identification_data'
--                OR it ? 'nutrition_data'
--                OR (
--                     jsonb_typeof(it -> 'analysis') = 'object'
--                     AND (
--                         (it -> 'analysis') ? 'phase'
--                      OR (it -> 'analysis') ? 'identification_data'
--                      OR (it -> 'analysis') ? 'nutrition_data'
--                     )
--                )
--         )
--   );
--
-- COMMIT;
--
-- =============================================================================
-- End of migration 260422_rename_step_keys.sql
-- =============================================================================
