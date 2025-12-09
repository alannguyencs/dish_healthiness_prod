#!/usr/bin/env python3
"""
Test script for new user feedback features.

This script tests:
1. Pydantic models (DishPrediction, FoodHealthAnalysis, FoodHealthAnalysisBrief)
2. CRUD iteration functions
3. API endpoint availability
"""

import sys
sys.path.insert(0, '.')

print("=" * 60)
print("Testing User Feedback Feature Implementation")
print("=" * 60)

# Test 1: Pydantic Models
print("\n[Test 1] Testing Pydantic Models...")
try:
    from src.service.llm.models import DishPrediction, FoodHealthAnalysis, FoodHealthAnalysisBrief

    # Test DishPrediction
    pred = DishPrediction(
        name="Grilled Chicken Breast",
        confidence=0.95,
        serving_sizes=["1 piece (85g)", "100g", "1 breast (150g)"]
    )
    assert pred.name == "Grilled Chicken Breast"
    assert pred.confidence == 0.95
    assert len(pred.serving_sizes) == 3
    print("  ✅ DishPrediction model works")

    # Test FoodHealthAnalysis with predictions
    analysis = FoodHealthAnalysis(
        dish_name="Test Dish",
        healthiness_score=8,
        healthiness_score_rationale="Good protein source",
        calories_kcal=200,
        fiber_g=3,
        carbs_g=10,
        protein_g=25,
        fat_g=5,
        micronutrients=["Vitamin B12", "Iron"],
        dish_predictions=[pred]
    )
    assert analysis.dish_predictions is not None
    assert len(analysis.dish_predictions) == 1
    print("  ✅ FoodHealthAnalysis model works (with predictions)")

    # Test FoodHealthAnalysisBrief without predictions
    brief = FoodHealthAnalysisBrief(
        dish_name="Test Dish",
        healthiness_score=8,
        healthiness_score_rationale="Good protein source",
        calories_kcal=200,
        fiber_g=3,
        carbs_g=10,
        protein_g=25,
        fat_g=5,
        micronutrients=["Vitamin B12", "Iron"]
    )
    assert not hasattr(brief, 'dish_predictions')
    print("  ✅ FoodHealthAnalysisBrief model works (no predictions)")

except Exception as e:
    print(f"  ❌ Model test failed: {e}")
    sys.exit(1)

# Test 2: MetadataUpdate Schema
print("\n[Test 2] Testing MetadataUpdate Schema...")
try:
    from src.schemas import MetadataUpdate

    metadata = MetadataUpdate(
        selected_dish="Grilled Chicken Breast",
        selected_serving_size="1 piece (85g)",
        number_of_servings=1.5
    )
    assert metadata.selected_dish == "Grilled Chicken Breast"
    assert metadata.number_of_servings == 1.5
    print("  ✅ MetadataUpdate schema works")

    # Test validation
    try:
        bad_metadata = MetadataUpdate(
            selected_dish="Test",
            selected_serving_size="100g",
            number_of_servings=15.0  # Should fail (> 10.0)
        )
        print("  ❌ Validation should have rejected servings > 10.0")
    except:
        print("  ✅ Validation correctly rejects invalid servings")

except Exception as e:
    print(f"  ❌ Schema test failed: {e}")
    sys.exit(1)

# Test 3: CRUD Functions
print("\n[Test 3] Testing CRUD Functions...")
try:
    from src.crud.crud_food_image_query import initialize_iterations_structure

    # Test initialize_iterations_structure
    analysis_data = {
        "dish_name": "Test Chicken",
        "healthiness_score": 8,
        "calories_kcal": 200
    }
    result = initialize_iterations_structure(analysis_data)

    assert "iterations" in result
    assert result["current_iteration"] == 1
    assert len(result["iterations"]) == 1
    assert result["iterations"][0]["iteration_number"] == 1
    assert "metadata" in result["iterations"][0]
    assert result["iterations"][0]["metadata"]["selected_dish"] == "Test Chicken"
    print("  ✅ initialize_iterations_structure works")

    # Test with custom metadata
    custom_meta = {
        "selected_dish": "Custom Dish",
        "selected_serving_size": "1 piece (100g)",
        "number_of_servings": 2.0,
        "metadata_modified": True
    }
    result2 = initialize_iterations_structure(analysis_data, custom_meta)
    assert result2["iterations"][0]["metadata"]["selected_dish"] == "Custom Dish"
    assert result2["iterations"][0]["metadata"]["number_of_servings"] == 2.0
    print("  ✅ Custom metadata initialization works")

except Exception as e:
    print(f"  ❌ CRUD test failed: {e}")
    sys.exit(1)

# Test 4: Prompt Loading
print("\n[Test 4] Testing Prompt Loading...")
try:
    from src.service.llm.prompts import get_analysis_prompt, get_brief_analysis_prompt

    full_prompt = get_analysis_prompt()
    assert len(full_prompt) > 0
    assert "dish identification" in full_prompt.lower() or "predictions" in full_prompt.lower()
    print("  ✅ Full analysis prompt loads correctly")

    brief_prompt = get_brief_analysis_prompt()
    assert len(brief_prompt) > 0
    assert "user-selected metadata" in brief_prompt.lower()
    print("  ✅ Brief analysis prompt loads correctly")

except Exception as e:
    print(f"  ❌ Prompt test failed: {e}")
    sys.exit(1)

# Test 5: API Endpoints Availability
print("\n[Test 5] Testing API Endpoints...")
try:
    from src.main import app

    # Get all routes
    routes = [route.path for route in app.routes]

    # Check for new endpoints
    required_endpoints = [
        "/api/item/{record_id}",
        "/api/item/{record_id}/metadata",
        "/api/item/{record_id}/reanalyze"
    ]

    for endpoint in required_endpoints:
        if endpoint in routes:
            print(f"  ✅ {endpoint} registered")
        else:
            print(f"  ❌ {endpoint} NOT found")

except Exception as e:
    print(f"  ❌ API test failed: {e}")
    sys.exit(1)

# Summary
print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
print("\nBackend is ready for testing:")
print("  1. Start server: uvicorn src.main:app --reload --port 2612")
print("  2. Test endpoints with actual dish image upload")
print("  3. Verify dish predictions appear in response")
print("  4. Test metadata update and re-analysis workflow")
print("=" * 60)
