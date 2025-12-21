import React from "react";

/**
 * Step2Results Component
 *
 * Displays Step 2 nutritional analysis results after user confirmation.
 */
const Step2Results = ({ step2Data }) => {
  if (!step2Data) {
    return (
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-blue-800">Step 2 analysis in progress...</p>
      </div>
    );
  }

  const {
    dish_name,
    healthiness_score,
    healthiness_score_rationale,
    calories_kcal,
    fiber_g,
    carbs_g,
    protein_g,
    fat_g,
    micronutrients = [],
  } = step2Data;

  // Color coding for healthiness score
  const getScoreColor = (score) => {
    if (score >= 81) return "text-green-600 bg-green-100";
    if (score >= 61) return "text-green-500 bg-green-50";
    if (score >= 41) return "text-yellow-600 bg-yellow-100";
    if (score >= 21) return "text-orange-600 bg-orange-100";
    return "text-red-600 bg-red-100";
  };

  const getScoreLabel = (score) => {
    if (score >= 81) return "Very Healthy";
    if (score >= 61) return "Healthy";
    if (score >= 41) return "Moderate";
    if (score >= 21) return "Unhealthy";
    return "Very Unhealthy";
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6 space-y-6">
      <div className="border-b pb-4">
        <h2 className="text-2xl font-bold text-gray-800">
          Step 2: Nutritional Analysis
        </h2>
        <p className="text-lg text-gray-600 mt-1">{dish_name}</p>
      </div>

      {/* Healthiness */}
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold text-gray-800">Healthiness</h3>
          <div
            className={`px-3 py-1.5 rounded-lg text-base font-semibold ${getScoreColor(healthiness_score)}`}
          >
            {getScoreLabel(healthiness_score)}
          </div>
        </div>
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <p className="text-gray-700 leading-relaxed">
            {healthiness_score_rationale}
          </p>
        </div>
      </div>

      {/* Macronutrients Summary */}
      <div className="space-y-2">
        <h3 className="text-lg font-semibold text-gray-800 mb-3">
          Nutritional Information
        </h3>

        <div className="space-y-1">
          {/* Calories and Fiber */}
          <div className="flex items-center justify-between py-2 border-b border-gray-200">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <span className="text-lg">🔥</span>
                <span className="text-gray-700">Calories (kcal)</span>
                <span className="font-semibold text-gray-800">
                  {calories_kcal}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-lg">🌾</span>
                <span className="text-gray-700">Fiber (g)</span>
                <span className="font-semibold text-gray-800">{fiber_g}</span>
              </div>
            </div>
          </div>

          {/* Carbs, Protein, Fat */}
          <div className="flex items-center justify-between py-2 border-b border-gray-200">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <span className="text-lg">🍞</span>
                <span className="text-gray-700">Carbs (g)</span>
                <span className="font-semibold text-gray-800">{carbs_g}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-lg">🍖</span>
                <span className="text-gray-700">Protein (g)</span>
                <span className="font-semibold text-gray-800">{protein_g}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-lg">🧈</span>
                <span className="text-gray-700">Fat (g)</span>
                <span className="font-semibold text-gray-800">{fat_g}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Micronutrients */}
      {micronutrients.length > 0 && (
        <div className="py-2 border-b border-gray-200">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="text-lg">🍊</span>
              <span className="text-gray-700">Micronutrients</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {micronutrients.map((nutrient, idx) => (
                <span
                  key={idx}
                  className="px-2 py-1 bg-purple-50 border border-purple-200 text-purple-700 rounded text-xs font-medium"
                >
                  {nutrient}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Cost/Token Info */}
      {(step2Data.model || step2Data.price_usd || step2Data.analysis_time) && (
        <div className="pt-4 border-t text-sm text-gray-500">
          <div className="flex items-center gap-6">
            {step2Data.model && (
              <div className="flex items-center gap-1.5">
                <span>🤖</span>
                <span>Model:</span>
                <span className="font-medium">{step2Data.model}</span>
              </div>
            )}
            {step2Data.price_usd && (
              <div className="flex items-center gap-1.5">
                <span>💰</span>
                <span>Cost:</span>
                <span className="font-medium">
                  ${step2Data.price_usd.toFixed(4)}
                </span>
              </div>
            )}
            {step2Data.analysis_time && (
              <div className="flex items-center gap-1.5">
                <span>⏱️</span>
                <span>Time:</span>
                <span className="font-medium">{step2Data.analysis_time}s</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Step2Results;
