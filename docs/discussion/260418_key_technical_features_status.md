# Discussion — Key In-Depth Technical Features (5 checkboxes)

**Question:** For each of the 5 items under "Key In-Depth Technical Features", decide Done / Not Done and list missing pieces.

1. Curated Nutrition Database Lookup
2. Multi-Stage Database Search
3. Multi-Source Evidence Fusion
4. Cooking Method and Regional Variant Context
5. Nutritional Consistency Evaluation

**Verdict summary:**

| # | Item | Status |
|---|------|--------|
| 1 | Curated Nutrition Database Lookup | **Not Done** |
| 2 | Multi-Stage Database Search | **Not Done** |
| 3 | Multi-Source Evidence Fusion | **Not Done** (only image evidence is fused) |
| 4 | Cooking Method and Regional Variant Context | **Not Done** (cooking method ✓; regional variant not in active prompts) |
| 5 | Nutritional Consistency Evaluation | **Done** |

These five lines are the most "marketing-heavy" entries in the feature list — they describe an architecture (RAG over a curated nutrition DB, multi-stage retrieval, evidence fusion across sources) that the current implementation does not have. The actual pipeline is two single-shot Gemini multimodal calls with no retrieval layer.

---

## How I checked

- Searched the entire `backend/src/` tree for `nutrition_database`, `food_database`, `USDA`, `FDC`, `nutritionix`, `edamam` — no matches outside prompt text.
- Read both active prompt files (`backend/resources/step1_component_identification.md`, `step2_nutritional_analysis.md`) end-to-end.
- Confirmed there are only two LLM calls in the pipeline: `analyze_step1_component_identification_async` and `analyze_step2_nutritional_analysis_async` (technical docs + `gemini_analyzer.py`).
- Searched for `prior`, `previous user`, `history`, `user-similar` in `backend/src` — no retrieval-style code.
- Found two **orphan** prompt files (`food_analysis.md`, `food_analysis_brief.md`) that do contain "regional/cuisine" wording, but `grep food_analysis backend/src` returns **no matches** — they are not loaded by any code.

## Per-item verdict

### 1. Curated Nutrition Database Lookup → Not Done

**Claim:** "The agent queries a structured nutrition database of dishes and nutrient values, rather than relying only on computer vision direct estimation."

**Reality:**
- No structured nutrition DB exists in the project. No `nutrition` / `food_composition` / `usda_*` table or external client.
- The Step 2 prompt *tells* Gemini to "Use standard food composition databases (USDA, nutritional references)", but this is just instructing the LLM to draw on its training knowledge. There is no actual query, no API call, no embedding lookup.

**Missing pieces to claim Done:**
- A real nutrition reference store — either a local table seeded from USDA FoodData Central (or similar), or an integration with an external nutrition API (USDA FDC, Nutritionix, Edamam).
- A retrieval step that turns a confirmed component name + serving size into one or more candidate rows from that store, before/around the LLM call.
- Schema/migration + seed pipeline for the data.

### 2. Multi-Stage Database Search → Not Done

**Claim:** "Composed search strategies in multiple stages to better find relevant information for nutritional evaluation as well as confidence scores to adequately rank query results."

**Reality:** Depends on (1). With no DB, there is no search, single- or multi-stage. No ranking, no confidence scores attached to retrieval results.

**Missing pieces to claim Done:**
- Same prerequisite: a nutrition reference store.
- A search orchestrator with multiple strategies, e.g. exact-name → fuzzy-name → component-keyword → embedding search, with each stage's results scored and merged.
- A confidence/score attached to each retrieved row, exposed somewhere visible (logs, response, or LLM input).

### 3. Multi-Source Evidence Fusion → Not Done

**Claim:** "Combines database results, AI image analysis, and optional prior user-like dish information into one unified estimate."

**Reality:**
- **Image analysis** ✓ — that's Phase 1 + Phase 2.
- **Database results** ✗ — see (1).
- **Prior user-like dish information** ✗ — there is no code that reads prior `DishImageQuery` rows for the same/similar dish and feeds them as context. No user-history retrieval, no embedding similarity, nothing in `service/` or `crud/` matching this.

The current "fusion" is sequential, not multi-source: image → AI proposes → user confirms → image + confirmed text → AI scores. Only one source of evidence (the image, plus user edits over its output).

**Missing pieces to claim Done:**
- DB retrieval (per item 1).
- A "user dish history" retrieval — given the confirmed dish name/components, look up similar prior records for the same user (or globally) and inject summary stats (typical calories for "Beef Burger by this user" = X) into the Step 2 prompt.
- A merging policy that decides how to weight DB vs image vs prior — even a simple "if DB hit, prefer DB calories ± image-based portion adjustment" would qualify.

### 4. Cooking Method and Regional Variant Context → Not Done

**Claim:** "In the analysis information about the cooking style, preparation method, and regional variant are taken into account."

**Reality, split into two parts:**

- **Cooking method ✓** — `step2_nutritional_analysis.md` explicitly:
  - lists "Health-Conscious Cooking Method" as a healthiness criterion (steamed/baked/grilled/poached vs deep-fried/charred);
  - has "Account for cooking methods" calculation guideline (boiling, roasting, deep-frying, grilling — with weight/oil-uptake adjustments).
- **Regional variant ✗** — neither active prompt (`step1_component_identification.md`, `step2_nutritional_analysis.md`) mentions regional cuisine, cultural variants, or preparation regional-norms.
  - The strings "regional", "cuisine", "variant" only appear in **orphan** files `backend/resources/food_analysis.md` and `food_analysis_brief.md`, which are **not loaded by any code path** (`grep food_analysis backend/src` returns nothing).
  - So while the supporting prose exists in the repo, it does not influence any Gemini call today.

Because the issue line conjuncts cooking *and* regional variant, the literal claim is not met.

**Missing pieces to claim Done:**
- Add a "Cuisine / regional context" block to `step2_nutritional_analysis.md` (and arguably `step1_component_identification.md`) instructing Gemini to consider regional preparation norms.
- Or wire one of the orphan prompts (`food_analysis.md`) into the active pipeline if its broader rubric is the intended target.

### 5. Nutritional Consistency Evaluation → Done

**Claim:** "Technical internal guidelines for adequate nutritional assessment are applied to ensure higher plausibility in the estimated outputs."

**Reality:**
- `step2_nutritional_analysis.md` carries an explicit "Theoretical Framework" with 11 healthiness criteria, a 5-step calculation method, "Step 3: Validate against dish image" (sanity check totals against the visible portion), "Step 4: Be precise but realistic", a 5-band score scale (0-20 / 21-40 / ... / 81-100), and explicit "Important Guidelines" for cooking-method adjustments and sauces/oils.
- Pydantic schema (`Step2NutritionalAnalysis`) enforces `ge=0` floors on every numeric field and `0 ≤ healthiness_score ≤ 100` — basic structural plausibility.

These count as "internal guidelines for nutritional assessment" applied through prompt + schema validation. ✓

## Recommendation

- Tick **only #5** (`Nutritional Consistency Evaluation`).
- Leave #1, #2, #3, #4 unchecked. Each has a concrete gap documented above so the team can either (a) build the missing capability or (b) reword the PDF to match what's actually shipped. Both are reasonable; this is the typical marketing-vs-reality drift for an MVP.

Suggested follow-ups if the team wants to honor the literal wording later:

- New feature plan: "Add nutrition DB + retrieval (USDA FDC integration)" — covers items 1, 2, and the DB leg of 3.
- New feature plan: "Inject user dish history into Step 2 prompt" — covers the user-history leg of 3.
- Small prompt update: add a "Regional / cuisine variant" guideline to `step2_nutritional_analysis.md` — covers the regional leg of 4. This is low-risk and could be a quick win.

## Pipeline (Current State)

### Current State

```
[User] Uploads photo
   │
   ▼
[Backend] Phase 1: Gemini multimodal call on image
   │   (no DB lookup, no retrieval)
   │
   ▼
[User] Reviews + edits dish name, components, servings
   │
   ▼
[Backend] Phase 2: Gemini multimodal call on
            image + confirmed-data text block
   │   (no DB lookup, no user-history injection,
   │    no retrieval at all)
   │
   ▼
[Backend] Persist Step2NutritionalAnalysis to result_gemini.step2_data
   │
   ▼
[Frontend] Step2Results renders score + macros + micros
```

### New State

_Pending comments._

## Next Steps

- Tick item #5 in `docs/issues/260414.md`; leave #1–#4 unchecked.
- Decide whether to (a) build the missing DB/retrieval/fusion capabilities, or (b) reword these four PDF lines to describe the actual shipped behavior. If (a), use `/feature-plan` for the DB integration first — items 1, 2, and most of 3 collapse into one initiative.
