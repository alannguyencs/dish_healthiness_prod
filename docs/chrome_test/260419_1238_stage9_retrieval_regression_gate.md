# Chrome E2E Test Spec — Stage 9: Retrieval Regression Gate

**Status: SKIPPED (no UI, no observable HTTP behavior)**

---

## Why this spec is empty

Stage 9 ships:

1. `backend/tests/data/retrieval_eval_dataset.csv` — a 846-query labeled eval set.
2. `backend/tests/test_nutrition_retrieval_benchmark.py` — a pytest benchmark that asserts aggregate NDCG@10 ≥ 0.75 when run with the `benchmark` marker.

There is no new HTTP endpoint, no schema change, no DOM change, and no user-visible behavior. The Chrome Claude Extension harness has nothing to click. Same rationale as Stages 0 and 1 of the 260415 issue — both of those skipped Chrome tests for the identical reason (pure library / CI additions with zero user surface).

## How to exercise Stage 9 manually

Skip Chrome entirely. The acceptance check from the issue is:

```bash
source venv/bin/activate
cd backend
python -m scripts.seed.load_nutrition_db   # if nutrition_foods is empty
pytest backend/tests/test_nutrition_retrieval_benchmark.py -m benchmark
```

Expected output: the test emits NDCG@10 (anchor: reference project measured 0.7744 on the same eval set) and passes the `>= 0.75` floor.

## If a future stage adds a user-facing benchmark dashboard

Generate a real Chrome spec at that time. Stage 9 as planned does not need one.
