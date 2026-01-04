# Workflow: Test Custom Dish Name

## Objective
Test the custom dish name functionality in Step 1 of dish analysis.

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
- From dashboard, click on an empty date (e.g., January 5, 2026)

### 3. Upload Image via URL
- Click "Or paste image URL" under Dish 1
- Enter URL: `http://localhost:2612/images/260104_124346_dish1.jpg`
- Click "Load" button
- Wait for Step 1 analysis to complete

### 4. Test Custom Dish Name
- In "Overall Meal Name" section, select "Custom Dish Name" radio button
- Enter custom name: `My Homemade Burger Combo`
- Verify the text input accepts the custom name

### 5. Confirm and Proceed
- Click "Confirm and Analyze Nutrition" button
- Wait for Step 2 analysis to complete

### 6. Verify Results
- Confirm Step 2 shows the custom dish name: "My Homemade Burger Combo"
- Verify nutritional analysis completed successfully

## Expected Results
- Custom dish name should be displayed in Step 2 results
- Nutritional analysis should use the custom name for the meal
- All other analysis data (components, nutrition) should remain accurate
