## Personalization Matches (top 5, this user's prior dishes)

The following are previous uploads by the same user whose caption or confirmed dish name overlaps this query. Treat `prior_nutrition_data` as weaker evidence than the Nutrition Database above — the user's prior analysis may itself have been uncertain.

**When `corrected_nutrition_data` is present, it is the user's hand-corrected nutrients — treat it as AUTHORITATIVE for the query image's dish.** Specifically:

1. Derive the user's per-portion profile by dividing the corrected macros by the number of servings you estimate from the **user's** prior image (look at the match's `description` for context). Apply that per-portion profile to your estimate of the current image's portion count.
2. Preserve the user's `micronutrients` list verbatim unless the query image clearly shows different ingredients. If the user added a nutrient (e.g. Vitamin D) you do not recognize from the photo, keep it anyway — the user likely has context you cannot see.
3. If the user's `healthiness_score_rationale` reflects a durable preference (portion size, cooking method, ingredient swap), echo that reasoning in your own `healthiness_score_rationale` rather than describing the photo generically.
4. Cite the correction explicitly in `reasoning_sources` using the phrase "user-corrected" so downstream reviewers can tell.

```json
{{PAYLOAD_JSON}}
```
