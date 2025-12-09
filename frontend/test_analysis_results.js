/**
 * Test script to verify AnalysisResults component handles iterations format
 */

// Mock item data with iterations (new format)
const mockItemWithIterations = {
    id: 5,
    iterations: [
        {
            iteration_number: 1,
            analysis: {
                dish_name: "Cheeseburger",
                healthiness_score: 2,
                healthiness_score_rationale: "Low score due to processed ingredients...",
                calories_kcal: 283,
                fiber_g: 1,
                carbs_g: 28,
                protein_g: 15,
                fat_g: 12,
                micronutrients: ["Iron", "Vitamin B12", "Zinc", "Sodium"],
                model: "gemini-2.5-pro",
                input_token: 3500,
                output_token: 1200,
                price_usd: 0.0042,
                analysis_time: 4.5
            }
        }
    ],
    current_iteration: 1,
    result_gemini: {
        iterations: [/* same as above */],
        current_iteration: 1
    }
};

// Test extraction logic
function testAnalysisDataExtraction(item) {
    let geminiResult = {};

    if (item.iterations && item.iterations.length > 0) {
        // New format with iterations - get current iteration's analysis
        const currentIterIndex = (item.current_iteration || 1) - 1;
        const currentIter = item.iterations[currentIterIndex];
        geminiResult = currentIter?.analysis || {};
    } else if (item.result_gemini) {
        // Legacy format - direct result
        if (item.result_gemini.iterations) {
            // Wrapped in iterations but not exposed at top level
            const currentIterIndex = (item.result_gemini.current_iteration || 1) - 1;
            const currentIter = item.result_gemini.iterations[currentIterIndex];
            geminiResult = currentIter?.analysis || {};
        } else {
            // Pure legacy format
            geminiResult = item.result_gemini;
        }
    }

    return geminiResult;
}

console.log("Testing AnalysisResults data extraction...\n");

const result = testAnalysisDataExtraction(mockItemWithIterations);

console.log("✅ Extracted analysis data:");
console.log("  - dish_name:", result.dish_name);
console.log("  - healthiness_score:", result.healthiness_score);
console.log("  - calories_kcal:", result.calories_kcal);
console.log("  - model:", result.model);
console.log("  - input_token:", result.input_token);

if (result.dish_name === "Cheeseburger" &&
    result.healthiness_score === 2 &&
    result.calories_kcal === 283) {
    console.log("\n✅ TEST PASSED: Data extraction works correctly!");
} else {
    console.log("\n❌ TEST FAILED: Data extraction issue");
}
