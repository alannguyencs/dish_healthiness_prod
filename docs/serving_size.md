Each *standard measurement* below uses FDA metric equivalents (cup, tbsp, tsp, ounce), and each *hand measurement* is a practical visual estimate.

## Serving size — the simple version

**A serving size is the FDA's standard "one slot" for a food type, so calories on a label mean something consistent.**

Think of the Nutrition Facts label as a menu with prices. Without a standard portion, every brand would price differently ("$5 for some fries" — how much is *some*?). Serving size is FDA saying: "For fries, one serving = a medium handful. All brands list prices per that one handful."

### What it IS

- A **fixed reference amount** per food category (chicken breast = 3 oz, bacon = 1 slice, cereal = 1 cup, soda = 12 fl oz).
- Based on **how much people actually eat in one sitting**, from national consumption surveys.
- **Listed in both household units + grams** (e.g. "1 cup / 240 mL") so users can eyeball it.

### What it is NOT

- ❌ Not a recommendation of how much you *should* eat.
- ❌ Not a measurement of how much you *did* eat.
- ❌ Not universal across foods — each food category has its own.

### Why it exists (4 reasons)

1. **Humans don't weigh food.** "1 cup" is estimate-able by eye; "47 grams" is not.
2. **Density varies.** 1 cup of puffed rice = 14 g; 1 cup of granola = 112 g. Per-cup nutrition matches what the eye sees; per-gram is a lab number.
3. **Stops manufacturer tricks.** Before the FDA RACC table, brands shrank servings to claim "0 calories". The table locks it in per category.
4. **Compare brands at a glance.** All cereal boxes list "per ¾ cup", so 150 vs. 180 kcal means something immediately — no mental math.

### How to read a label correctly

```
┌─ Nutrition Facts ──────────────┐
│ Serving size     1 cup (45 g)  │   ← the FDA reference
│ Servings per box  10            │   ← how many servings the package holds
│ Calories          180           │   ← PER ONE serving (1 cup / 45 g)
└────────────────────────────────┘
```

Eat 2 cups → you ate 2 servings → **360 calories**. The label doesn't change; you multiply.

### One-line takeaway

> Serving size is a **ruler**, not a recommendation. The amount you actually ate is a separate number that you multiply the label numbers by.

### How it shows up in this app

| Concept | What it is | Where it lives in the pipeline |
|---|---|---|
| Serving size | FDA's reference weight for this food type | `step1_data.components[n].serving_sizes` (e.g. "3 oz", "4 oz", …) — the dropdown options on the Step 1 editor |
| User's portion count | How many of those reference servings are on the plate | `step1_data.components[n].number_of_servings` (and `confirmed_portions` post-confirm) |
| Total meal nutrition | `per_serving_nutrition × portion_count`, summed across components | `step2_data` computed by Phase 2.3 |

---

## Bread, cereal, rice, pasta

| Dish category | Standard measurement (FDA / USDA) | Hand / finger estimate |
| --- | --- | --- |
| Bread slice | 1 slice bread ≈ 1 serving (about 1 oz ≈ 28 g). | Size of your **flat palm** from base of fingers to mid‑finger, thickness of a normal slice. |
| Ready‑to‑eat cereal | 1 ounce cereal (28 g) = 1 serving; volume varies by cereal shape. | About **one cupped hand** of flakes or puffs. |
| Cooked cereal / rice / pasta | 1/2 cup cooked = 1 serving. 1/2 cup = 120 mL. | 1/2 cup ≈ **one cupped hand** (not tightly packed). |

## Vegetables

| Dish category | Standard measurement | Hand / finger estimate |
| --- | --- | --- |
| Raw leafy vegetables | 1 cup raw leafy veg = 1 serving (240 mL). | ~ size of **one closed fist** piled loosely. |
| Other vegetables (cooked or chopped raw) | 1/2 cup = 1 serving (120 mL). | **One cupped hand** of pieces. |
| Vegetable juice | 3/4 cup = 1 serving (180 mL). | A bit less than a **full fist** of liquid in a small glass. |

## Fruit

| Dish category | Standard measurement | Hand / finger estimate |
| --- | --- | --- |
| Whole fruit | 1 medium apple/banana/orange = 1 serving (about 1 piece). | A fruit about the size of your **fist**. |
| Chopped / cooked / canned fruit | 1/2 cup = 1 serving (120 mL). | **One cupped hand** of fruit pieces. |
| Fruit juice | 3/4 cup = 1 serving (180 mL). | Juice filling a small glass about **three‑quarters of a fist** high. |

## Milk, yogurt, cheese

| Dish category | Standard measurement | Hand / finger estimate |
| --- | --- | --- |
| Milk or yogurt | 1 cup = 1 serving (240 mL). | Liquid or spoonable food filling a mug roughly the size of your **fist**. |
| Natural cheese | 1½ oz = 1 serving; 1 oz = 28 g ⇒ 1½ oz ≈ 42 g. | About **two thumb‑sized** cubes of cheese. |
| Process cheese | 2 oz = 1 serving (≈ 56 g). | Roughly **three thumb‑sized** pieces or a slice stack the size of two thumbs side‑by‑side. |

## Meat, poultry, fish, dry beans, eggs, nuts

| Dish category | Standard measurement | Hand / finger estimate |
| --- | --- | --- |
| Lean meat, poultry, fish (per serving) | 2–3 oz cooked lean meat/poultry/fish = 1 serving. 1 oz = 28 g. | 2–3 oz ≈ **palm of your hand** (length and width, thickness of a deck of cards). |
| Daily meat‑group total | 5–7 oz cooked lean meat (or equivalent) per day. | About **2–3 palm‑sized** portions across the day. |
| Cooked dry beans | 1/2 cup beans = 1 oz meat equivalent. So 1½ cups beans ≈ 3 oz meat. | 1/2 cup ≈ **one cupped hand** of beans. |
| Egg | 1 egg = 1 oz meat equivalent. | One **whole egg** about the size of your palm center. |
| Peanut butter | 2 tbsp peanut butter = 1 oz meat equivalent. 1 tbsp = 15 mL. | 2 tbsp ≈ length and thickness of **your whole thumb** spread twice (two thumbfuls). |

## Quick reference for the measurement units

- 1 cup = 240 mL; 1 tablespoon = 15 mL; 1 teaspoon = 5 mL; 1 fluid ounce = 30 mL; 1 ounce (weight) = 28 g.
- Fist ≈ 1 cup; cupped hand ≈ 1/2 cup; palm (no fingers) ≈ 2–3 oz of meat; thumb ≈ 1 tbsp; thumb tip ≈ 1 tsp.

## References
- [US Standard Measurement](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/guidance-industry-guidelines-determining-metric-equivalents-household-measures)
- [Estimation using hand](https://www.siue.edu/campus-recreation/facilities/EstimatingPortionSizesUsingYourHands.pdf)
- food_guide_pyramid.pdf document