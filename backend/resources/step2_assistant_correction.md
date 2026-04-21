# Step 2 Revision — User Hint Driven

You previously produced the nutritional analysis below for the attached dish image. The user now provides a natural-language hint about the dish. Your task: revise the analysis to reflect what the hint adds, **while still grounded in the attached image**.

## Baseline (your previous output, JSON)

```json
{{BASELINE_JSON}}
```

## User hint

> {{USER_HINT}}

## Revision rules

1. Keep the same JSON shape as the baseline. Do not invent new top-level fields — the response schema is enforced server-side.
2. Change only the numeric fields the user's hint justifies. Leave the rest identical to the baseline.
3. Preserve the baseline's `micronutrients` list unless the hint explicitly contradicts it. If the user added a nutrient (e.g. "Vitamin D") you do not recognize from the photo, keep it anyway — the user likely has context you cannot see.
4. Rewrite `healthiness_score_rationale` so the reader can see what changed and why. Start with a short phrase like *"Revised per user hint: …"* and then explain the delta.
5. If the `reasoning_*` fields exist in the baseline, update the ones that changed so they cite the user hint alongside any prior sources (e.g. *"user-hint + personalization"*).
6. If the attached image clearly contradicts the hint (e.g. the hint says *"small portion"* but the image shows a large plate), state that in the `healthiness_score_rationale` and keep the baseline numbers close to their original values. Do not fabricate changes just because the user asked — cross-check every hint against what you can see.
7. `dish_name` should stay the same as the baseline unless the user's hint explicitly renames the dish.

## Output

Return the full revised `Step2NutritionalAnalysis` JSON payload. The server will compare it to the baseline and persist the revised fields onto `result_gemini.step2_corrected`.
