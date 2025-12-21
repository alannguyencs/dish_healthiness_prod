#!/usr/bin/env python3
"""
Test script for two-step dish analysis features.

This script tests:
1. Pydantic models (Step1ComponentIdentification, Step2NutritionalAnalysis)
2. CRUD iteration functions
3. API endpoint availability
4. Two-step prompt loading
"""

import sys

sys.path.insert(0, ".")

print("=" * 60)
print("Testing Two-Step Dish Analysis Implementation")
print("=" * 60)

# Test 1: Pydantic Models for Two-Step Analysis
print("\n[Test 1] Testing Step 1 and Step 2 Pydantic Models...")
try:
    from src.service.llm.models import (
        Step1ComponentIdentification,
        Step2NutritionalAnalysis,
        DishNamePrediction,
        ComponentServingPrediction,
    )

    # Test Step 1: Component Identification Model
    dish_pred = DishNamePrediction(name="Grilled Chicken Salad", confidence=0.95)
    component_pred = ComponentServingPrediction(
        component_name="Grilled Chicken Breast",
        serving_sizes=["1 piece (85g)", "100g", "1 breast (150g)"],
    )

    step1_result = Step1ComponentIdentification(
        dish_predictions=[dish_pred],
        components=[component_pred],
    )

    assert len(step1_result.dish_predictions) == 1
    assert step1_result.dish_predictions[0].name == "Grilled Chicken Salad"
    assert len(step1_result.components) == 1
    assert step1_result.components[0].component_name == "Grilled Chicken Breast"
    assert len(step1_result.components[0].serving_sizes) == 3
    print("  ✅ Step1ComponentIdentification model works")

    # Test Step 2: Nutritional Analysis Model
    step2_result = Step2NutritionalAnalysis(
        dish_name="Grilled Chicken Salad",
        healthiness_score=85,
        healthiness_score_rationale="High protein, low fat, good fiber from vegetables",
        calories_kcal=350,
        fiber_g=8,
        carbs_g=25,
        protein_g=40,
        fat_g=10,
        micronutrients=["Vitamin A", "Vitamin C", "Iron", "Calcium"],
    )

    assert step2_result.dish_name == "Grilled Chicken Salad"
    assert step2_result.healthiness_score == 85
    assert step2_result.calories_kcal == 350
    assert len(step2_result.micronutrients) == 4
    print("  ✅ Step2NutritionalAnalysis model works")

    # Test validation
    try:
        bad_step2 = Step2NutritionalAnalysis(
            dish_name="Test",
            healthiness_score=150,  # Should fail (> 100)
            healthiness_score_rationale="Test",
            calories_kcal=100,
            fiber_g=5,
            carbs_g=10,
            protein_g=20,
            fat_g=5,
            micronutrients=[],
        )
        print("  ❌ Validation should have rejected healthiness_score > 100")
    except Exception:
        print("  ✅ Validation correctly rejects invalid healthiness_score")

except Exception as e:
    print(f"  ❌ Model test failed: {e}")
    sys.exit(1)

# Test 2: Component Confirmation Request Schema
print("\n[Test 2] Testing Step1 Confirmation Schemas...")
try:
    from src.api.item_schemas import ComponentConfirmation, Step1ConfirmationRequest

    component_conf = ComponentConfirmation(
        component_name="Grilled Chicken Breast",
        selected_serving_size="1 piece (85g)",
        number_of_servings=1.5,
    )
    assert component_conf.component_name == "Grilled Chicken Breast"
    assert component_conf.number_of_servings == 1.5
    print("  ✅ ComponentConfirmation schema works")

    confirmation_req = Step1ConfirmationRequest(
        selected_dish_name="Grilled Chicken Salad",
        components=[component_conf],
    )
    assert confirmation_req.selected_dish_name == "Grilled Chicken Salad"
    assert len(confirmation_req.components) == 1
    print("  ✅ Step1ConfirmationRequest schema works")

    # Test validation
    try:
        bad_component = ComponentConfirmation(
            component_name="Test",
            selected_serving_size="100g",
            number_of_servings=15.0,  # Should fail (> 10.0)
        )
        print("  ❌ Validation should have rejected servings > 10.0")
    except Exception:
        print("  ✅ Validation correctly rejects invalid servings")

except Exception as e:
    print(f"  ❌ Schema test failed: {e}")
    sys.exit(1)

# Test 3: Two-Step Prompt Loading
print("\n[Test 3] Testing Step 1 and Step 2 Prompt Loading...")
try:
    from src.service.llm.prompts import (
        get_step1_component_identification_prompt,
        get_step2_nutritional_analysis_prompt,
    )

    # Test Step 1 prompt
    step1_prompt = get_step1_component_identification_prompt()
    assert len(step1_prompt) > 0
    assert (
        "component" in step1_prompt.lower()
        or "dish" in step1_prompt.lower()
        or "serving" in step1_prompt.lower()
    )
    print("  ✅ Step 1 component identification prompt loads correctly")

    # Test Step 2 prompt
    test_components = [
        {
            "component_name": "Grilled Chicken Breast",
            "selected_serving_size": "1 piece (85g)",
            "number_of_servings": 1.5,
        }
    ]
    step2_prompt = get_step2_nutritional_analysis_prompt(
        dish_name="Grilled Chicken Salad", components=test_components
    )
    assert len(step2_prompt) > 0
    assert "Grilled Chicken Salad" in step2_prompt
    assert "Grilled Chicken Breast" in step2_prompt
    print("  ✅ Step 2 nutritional analysis prompt loads and formats correctly")

except Exception as e:
    print(f"  ❌ Prompt test failed: {e}")
    sys.exit(1)

# Test 4: API Endpoints Availability
print("\n[Test 4] Testing API Endpoints...")
try:
    from src.main import app

    # Get all routes
    routes = [route.path for route in app.routes]

    # Check for two-step workflow endpoints
    required_endpoints = [
        "/api/item/{record_id}",
        "/api/item/{record_id}/metadata",
        "/api/item/{record_id}/confirm-step1",
    ]

    all_found = True
    for endpoint in required_endpoints:
        if endpoint in routes:
            print(f"  ✅ {endpoint} registered")
        else:
            print(f"  ❌ {endpoint} NOT found")
            all_found = False

    # Check date endpoints
    date_endpoints = ["/api/date/{year}/{month}/{day}", "/api/date/{year}/{month}/{day}/upload"]

    for endpoint in date_endpoints:
        if endpoint in routes:
            print(f"  ✅ {endpoint} registered")
        else:
            print(f"  ❌ {endpoint} NOT found")
            all_found = False

    if not all_found:
        sys.exit(1)

except Exception as e:
    print(f"  ❌ API test failed: {e}")
    sys.exit(1)

# Summary
print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
print("\nBackend is ready for two-step analysis workflow:")
print("  1. Start server: uvicorn src.main:app --reload --port 2612")
print("  2. Upload dish image to trigger Step 1 analysis")
print("  3. Review Step 1 results (dish predictions and components)")
print("  4. Confirm Step 1 data to trigger Step 2 analysis")
print("  5. View Step 2 nutritional analysis results")
print("=" * 60)
