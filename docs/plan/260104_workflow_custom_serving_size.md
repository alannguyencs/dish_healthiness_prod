# Workflow: Test Custom Serving Size

## Objective
Test the custom serving size functionality in Step 1 of dish analysis.

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
- From dashboard, click on an empty date (e.g., January 6, 2026)

### 3. Upload Image via URL
- Click "Or paste image URL" under Dish 1
- Enter URL: `http://localhost:2612/images/260104_124346_dish1.jpg`
- Click "Load" button
- Wait for Step 1 analysis to complete

### 4. Test Custom Serving Size
- In "Individual Dishes" section, locate the "Cheeseburger" component
- Click on the Serving Size dropdown (showing "4 oz")
- Select "Custom..." option from the dropdown
- Enter custom serving size: `6 oz (large patty)`
- Verify the custom text input appears and accepts the value

### 5. Optionally Test Second Component
- Locate the "French Fries" component
- Change serving size dropdown to "Custom..."
- Enter custom serving size: `1 cup`

### 6. Confirm and Proceed
- Click "Confirm and Analyze Nutrition" button
- Wait for Step 2 analysis to complete

### 7. Verify Results
- Confirm Step 2 nutritional analysis completed
- Verify the analysis considers the custom serving sizes
- Check that calorie/macro values reflect larger portions

## Expected Results
- Custom serving size input should be editable
- Cancel button (X) should revert to dropdown selection
- Step 2 analysis should use custom serving sizes for calculations
- Nutritional values should reflect the custom portions
