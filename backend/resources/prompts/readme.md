# Prompt templates

This directory holds every prompt text the backend sends to Gemini. Prompts
are split into two tiers:

- **Top-level prompts** (this directory) — one per LLM call. Loaded from
  disk, substituted with runtime data, and handed to the Gemini SDK.
- **Blocks** (`blocks/`) — reusable prose fragments that get inserted into
  top-level prompts when a data source is available and its confidence
  gate passes. A block whose data is missing or below-threshold is
  **stripped entirely** so the final prompt carries no empty heading.

## File inventory

| File | Phase | Role | Consumed by |
|---|---|---|---|
| `fast_caption.md` | 1.1.1 (a) | Flash caption of the uploaded dish image | `src/service/llm/fast_caption.py::_load_caption_instructions` |
| `component_identification.md` | 1.1.2 | Main Gemini 2.5 Pro call — identifies dish/components | `src/service/llm/prompts.py::get_component_identification_prompt` |
| `nutritional_analysis.md` | 2.3 | Main Gemini 2.5 Pro call — computes calories/macros/micros + healthiness | `src/service/llm/prompts.py::get_nutritional_analysis_prompt` |
| `nutrition_assistant_correction.md` | 2.4 (Button B) | AI-assisted nutrition revision driven by a user hint | `src/service/llm/nutrition_assistant.py::_render_assistant_prompt` |
| `blocks/reference_block.md` | 1.1.2 | Static "Reference results (HINT ONLY)" intro paragraph | appended into `component_identification.md` |
| `blocks/reference_block_user_edits.md` | 1.1.2 | Optional paragraph shown when the prior upload was user-confirmed in 1.2 | appended after the intro paragraph above |
| `blocks/nutrition_db_block.md` | 2.3 | Trimmed top-5 nutrition-DB matches (Malaysian / MyFCD / Anuvaad / CIQUAL) | substituted into `nutritional_analysis.md::__NUTRITION_DB_BLOCK__` |
| `blocks/personalized_block.md` | 2.3 | Trimmed top-5 user-history matches with prior + corrected nutrients | substituted into `nutritional_analysis.md::__PERSONALIZED_BLOCK__` |

## Placeholder conventions

Two styles live in these files, with different semantics:

| Style | Used for | Behavior on missing data |
|---|---|---|
| `__NAME__` (double underscore) | Optional block slots in top-level prompts | Placeholder line is **stripped entirely** via regex so no empty heading survives |
| `{{NAME}}` (double brace) | Required runtime values (JSON payloads, user hints) | Must always be substituted; a missing value is a bug |

## Integration diagrams

### Phase 1.1.2 — Component Identification

```
┌─────────────────────────────────────────────────────────────┐
│  component_identification.md                                │
│                                                             │
│  ... prompt body (sections, rules, output schema) ...       │
│                                                             │
│  __REFERENCE_BLOCK__  ← placeholder (stripped if no hint)   │
│                                                             │
│  ... more prompt body ...                                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌─────────────────┴─────────────────┐
         │    has prior reference dish?       │
         └───────┬───────────────────┬────────┘
                 │ yes                │ no
                 ▼                    ▼
   ┌──────────────────────────┐   ┌──────────────────────┐
   │  blocks/reference_       │   │  strip placeholder   │
   │  block.md                │   │  line entirely;      │
   │                          │   │  no "Reference       │
   │  "## Reference results   │   │  results" heading    │
   │  (HINT ONLY — may or     │   │  appears in the      │
   │  may not match) …"       │   │  prompt.             │
   └───────┬──────────────────┘   └──────────────────────┘
           │
           │  (if prior was user-confirmed in Phase 1.2)
           ▼
   ┌──────────────────────────┐
   │  blocks/reference_       │
   │  block_user_edits.md     │
   │                          │
   │  "The user manually      │
   │  corrected the prior     │
   │  dish's name and/or      │
   │  servings…"              │
   └───────┬──────────────────┘
           │
           ▼
   ┌──────────────────────────┐
   │  dynamic data rows        │
   │  (rendered in Python):    │
   │  • Prior dish name        │
   │  • Prior total servings   │
   │  • Prior components list  │
   └──────────────────────────┘
```

Assembler: `src/service/llm/prompts.py::_render_reference_block` loads
`blocks/reference_block.md`, optionally concatenates
`blocks/reference_block_user_edits.md`, then appends the dynamic data
rows. `get_component_identification_prompt` then either substitutes the
placeholder with the rendered block or strips the placeholder line when
the reference is missing.

### Phase 2.3 — Nutritional Analysis

```
┌─────────────────────────────────────────────────────────────┐
│  nutritional_analysis.md                                    │
│                                                             │
│  ... healthiness rubric, task description, guidelines ...   │
│                                                             │
│  __NUTRITION_DB_BLOCK__    ← gated on top match's           │
│                              confidence_score ≥ 80          │
│  __PERSONALIZED_BLOCK__    ← gated on top match's           │
│                              similarity_score ≥ 0.30        │
│                                                             │
│  ... attribution contract, output schema ...                │
└──────────────┬──────────────────────────┬───────────────────┘
               │                          │
               ▼                          ▼
 ┌──────────────────────────┐  ┌─────────────────────────────┐
 │  blocks/                 │  │  blocks/                    │
 │  nutrition_db_block.md   │  │  personalized_block.md      │
 │                          │  │                             │
 │  "## Nutrition Database  │  │  "## Personalization        │
 │   Matches (top 5, …)"    │  │   Matches (top 5, …)"       │
 │                          │  │                             │
 │  ```json                 │  │  ```json                    │
 │  {{PAYLOAD_JSON}}        │  │  {{PAYLOAD_JSON}}           │
 │  ```                     │  │  ```                        │
 └───────┬──────────────────┘  └───────┬─────────────────────┘
         │                             │
         ▼                             ▼
 ┌──────────────────────────┐  ┌─────────────────────────────┐
 │  trimmed top-5 matches   │  │  trimmed top-5 prior        │
 │  from `nutrition_db`     │  │  uploads + corrected data   │
 │  (source-aware macros)   │  │  (per-user BM25 retrieval)  │
 └──────────────────────────┘  └─────────────────────────────┘

 When a gate fails → placeholder line is stripped; no heading,
 no empty block. LLM sees a clean prompt with one less section.
```

Assemblers:
- `src/service/llm/_nutrition_blocks.py::render_nutrition_db_block` and
  `render_personalized_block` load each block file, check the gate,
  substitute `{{PAYLOAD_JSON}}` with the trimmed JSON, and return the
  rendered string (or `""` if gate fails).
- `src/service/llm/prompts.py::get_nutritional_analysis_prompt` loads
  `nutritional_analysis.md` and, for each placeholder, either substitutes
  the rendered block or strips the placeholder line via regex.

### Phase 2.4 Button B — AI Assistant Correction

```
┌─────────────────────────────────────────────────────────────┐
│  nutrition_assistant_correction.md                          │
│                                                             │
│  ... revision rules, "same JSON shape" contract ...         │
│                                                             │
│  {{BASELINE_JSON}}   ← required: current nutrition_data     │
│                        (or nutrition_corrected if present)  │
│                                                             │
│  {{USER_HINT}}       ← required: free-text user context     │
│                                                             │
│  ... output expectations, reasoning_* contract ...          │
└──────────────┬──────────────────────────┬───────────────────┘
               │                          │
               ▼                          ▼
 ┌──────────────────────────┐  ┌─────────────────────────────┐
 │  trimmed current         │  │  user-submitted hint text   │
 │  baseline JSON (semantic │  │  (e.g. "smaller portions —  │
 │  fields only; engineering│  │  ~200 kcal/serving")        │
 │  metadata dropped)       │  │                             │
 └──────────────────────────┘  └─────────────────────────────┘
```

Assembler:
`src/service/llm/nutrition_assistant.py::_render_assistant_prompt` loads
the template, drops engineering metadata from the baseline, and
substitutes both double-brace placeholders. No block files are consumed.

### Phase 1.1.1 (a) — Fast caption

`fast_caption.md` has no placeholders — it is a plain instruction read
verbatim by `src/service/llm/fast_caption.py::_load_caption_instructions`.

## Editing checklist

When you change one of these `.md` files:

1. Keep placeholder tokens byte-exact (`__NUTRITION_DB_BLOCK__`,
   `{{PAYLOAD_JSON}}`, etc.) — the Python assemblers look for literal
   strings.
2. If you move or rename a file, update the path constants in:
   - `src/service/llm/prompts.py`
   - `src/service/llm/_nutrition_blocks.py`
   - `src/service/llm/nutrition_assistant.py`
   - `src/service/llm/fast_caption.py`
3. Run the backend test suite — `test_prompts.py` and
   `test_nutrition_assistant.py` check the substitution/stripping
   behavior with byte-level string assertions, so even a stray newline
   change will surface.
