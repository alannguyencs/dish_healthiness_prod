# Workflow: Test Add Custom Component

## Objective
Test the add custom component functionality in Step 1 of dish analysis.

## Prerequisites
- Frontend running on port 2512
- Backend running on port 2612
- Test image available at: `http://localhost:2612/images/260104_124346_dish1.jpg`

## Test Steps

### 1. Login
- Navigate to `http://localhost:2512/login`
- Enter username: `alan`
- Enter password: `sunny`
- Click Login button

### 2. Navigate to Empty Date
- From dashboard, click on an empty date (e.g., January 7, 2026)

### 3. Upload Image via URL
- Click "Or paste image URL" under Dish 1
- Enter URL: `http://localhost:2612/images/260104_124346_dish1.jpg`
- Click "Load" button
- Wait for Step 1 analysis to complete

### 4. Add Custom Component
- In "Individual Dishes" section, click "+ Add Custom Component"
- Fill in the form:
  - Component Name: `Cola Drink`
  - Serving Size: `12 oz`
  - Number of Servings: `1`
- Click "Add" button
- Verify the new component appears in the list with "Manual" badge

### 5. Add Another Custom Component (Optional)
- Click "+ Add Custom Component" again
- Fill in the form:
  - Component Name: `Ketchup`
  - Serving Size: `2 tablespoon`
  - Number of Servings: `1`
- Click "Add" button

### 6. Test Remove Component
- Locate the manually added component
- Click "Remove" button next to it
- Verify the component is removed from the list

### 7. Re-add Component and Confirm
- Add back "Cola Drink" component (12 oz, 1 serving)
- Click "Confirm and Analyze Nutrition" button
- Wait for Step 2 analysis to complete

### 8. Verify Results
- Confirm Step 2 nutritional analysis completed
- Verify the analysis includes nutrition from:
  - Cheeseburger (AI detected)
  - French Fries (AI detected)
  - Cola Drink (manually added)
- Check total calories include the added beverage

## Expected Results
- Custom component form should appear when clicking "+ Add Custom Component"
- Validation should require both component name and serving size
- Manual components should display with "Manual" badge
- Remove button should only appear for manual components
- Step 2 analysis should include all components (AI + manual)
- Nutritional totals should include manually added items
