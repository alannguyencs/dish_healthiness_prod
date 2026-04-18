# MealSnap (1 Dish Healthiness Assessment Webapp) Full Feature List

The MealSnap (R&D internal name: 1 Dish Healthiness Assessment) web app helps people quickly track the main dishes they eat in their meals, such as lunch. Users take a photo of a **single main dish**, and the app identifies the dish and its components, then provides a healthiness score along with estimated calories and macronutrient values. If any errors are found, users can easily correct them, and the app generates updated, more accurate estimates. Dishes are logged in a monthly calendar so users can review their eating history over time.

The main features this Webapp provides to users are:

## Multimodal AI for Healthiness and nutrition assessment

- **Photo-Based Dish Analysis**: The AI agent analyzes an uploaded **dish image** directly, using multimodal vision to assess what food is present.
- **Automatic Dish Identification**: It determines the most likely **dish name** by combining image evidence with structured nutrition database matches.
- **Healthiness Category**: It produces a consolidated **healthiness category label** based on the final nutritional interpretation.
- **Healthiness rationale**: An explanation why the dish got that label is also provided.
- **Calorie estimation**: Total calories for the meal in kilocalories.
- **Fiber estimation**: Total dietary fibre in grams.
- **Carbohydrate estimation**: Total carbohydrates in grams.
- **Protein estimation**: Total protein in grams.
- **Fat estimation**: Total fat in grams.
- **Notable micronutrients**: A list of noteworthy vitamins and minerals the meal contains.

## Refining the results with manual corrections for difficult cases

- **Set the dish name**: The user can pick one of our application's proposed names or type a completely custom name when the suggestions are wrong.
- **Include or exclude detected components**: Each automatically detected components has a checkbox for inclusion.
- **Change the portion size**: The portion size for each component can be swapped via a dropdown.
- **Adjust portions**: The user can type a custom portion description when none of the suggestions fit and change how many portions of each component they actually ate.
- **Add a missed component**: Components our application failed to detect can be added manually.
- **Serving Size Helpful reference Guide**: A standalone reference page with common portion sizes to help the user to add better manual correct.

## Dish Recognition and Quantity Estimation

- **Dish name recognition**: Our application automatically analyses an uploaded photo and proposes up to five possible names for the overall dish, each with a likelihood score.
- **Individual-dish breakdown**: Our application lists the individual components visible on the dish, up to ten.
- **Portion size suggestions**: For the detected components, our application proposes three to five realistic portion size estimations (suggestions).
- **Predicted number of portions**: For every detected component, our application estimates how many portions are in the photo.

## Dishes history calendar and Logging dishes

- **Monthly calendar view**: A month-at-a-glance grid of everything the user has logged.
- **Up to five dishes per day**: Every calendar day offers five fixed slots for logging separate dishes.
- **Photo upload**: A dish can be logged by picking an image file from the device or by pasting the web address of a photo.

## Key In-Depth Technical Features

- **Curated Nutrition Database Lookup**: The agent queries a **structured nutrition database of dishes and nutrient values**, rather than relying only on computer vision direct estimation.
- **Multi-Stage Database Search**: It uses composed search strategies in multiple stages to better find relevant information for nutritional evaluation as well as confidence scores to adequately rank query results.
- **Multi-Source Evidence Fusion**: It combines **database results, AI image analysis, and optional prior user-like dish information** into one unified estimate.
- **Cooking Method and Regional Variant Context**: In the analysis information about the **cooking style, preparation method, and regional variant** are taken into account.
- **Nutritional Consistency Evaluation**: Technical internal guidelines for adequate nutritional assessment are applied to ensure higher plausibility in the estimated outputs.
