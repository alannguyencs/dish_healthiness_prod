# Dish Webapp — Feature List

Dish Healthiness is a web app for people who want a quick, honest read on what they are eating. A user snaps a photo of a meal, the app recognises the dish and its components, the user fine-tunes anything the automatic recognition got wrong, and then receives a healthiness score with macro- and micro-nutrient breakdowns. Meals are logged to a monthly calendar so the user can look back at their eating history over time.

## Meal history calendar

- **Monthly calendar view**: A month-at-a-glance grid of everything the user has logged.

## Adding a meal

- **Up to five meals per day**: Every calendar day offers five fixed slots for logging separate meals.
- **Photo upload**: A meal can be logged by picking an image file from the device or by pasting the web address of a photo.
- **Logged-meal thumbnail**: Each filled slot shows a thumbnail of the uploaded dish.

## Dish Recognition and Quantity Estimation

- **Dish name recognition**: Our application automatically analyses each uploaded photo and proposes up to five possible names for the overall dish, each with a sureness score.
- **Individual-dish breakdown**: Our application lists the individual dishes visible on the plate, up to ten.
- **Portion size suggestions**: For every detected dish, our application proposes three to five realistic portion descriptions.
- **Predicted number of portions**: For every detected dish, our application estimates how many portions are in the photo.

## Healthiness and nutrition

- **Overall healthiness score**: The meal gets a single score from 0 to 100.
- **Healthiness category label**: A colour-coded badge translates the score into a plain label.
- **Score rationale**: A short sentence explains why the meal got that score.
- **Calorie estimation**: Total calories for the meal in kilocalories.
- **Fiber estimation**: Total dietary fibre in grams.
- **Carbohydrate estimation**: Total carbohydrates in grams.
- **Protein estimation**: Total protein in grams.
- **Fat estimation**: Total fat in grams.
- **Notable micronutrients**: A list of noteworthy vitamins and minerals the meal contains.

## Refining the results with manual corrections

- **Set the dish name**: The user can pick one of our application's proposed names or type a completely custom name when the suggestions are wrong.
- **Include or exclude detected dishes**: Each automatically detected dish has a checkbox for inclusion.
- **Change the portion size**: The portion size for each dish can be swapped via a dropdown.
- **Adjust portions**: The user can type a custom portion description when none of the suggestions fit and change how many portions of each dish they actually ate.
- **Add a missed dish**: Dishes our application failed to detect can be added manually.

## Helpful reference

- **Serving Size Guide**: A standalone reference page with common portion sizes.
