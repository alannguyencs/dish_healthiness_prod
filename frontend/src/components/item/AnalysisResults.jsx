import React from 'react';

const AnalysisColumn = ({ title, result, colorClass }) => {
    if (!result) {
        return (
            <div className="flex-1 bg-gray-50 rounded-lg p-6 border border-gray-200">
                <h3 className={`text-xl font-bold mb-4 ${colorClass}`}>{title}</h3>
                <p className="text-gray-500">No analysis available</p>
            </div>
        );
    }

    const healthinessScore = result.healthiness_score?.healthiness_score;
    const rationale = result.healthiness_score?.rationale;

    return (
        <div className="flex-1 bg-white rounded-lg p-6 border-2 border-gray-200 shadow-sm">
            <h3 className={`text-xl font-bold mb-4 ${colorClass}`}>{title}</h3>
            
            {/* Dish Name */}
            {result.dish_name && (
                <div className="mb-4">
                    <h4 className="text-sm font-semibold text-gray-600 mb-1">Dish Name</h4>
                    <p className="text-lg font-medium">{result.dish_name}</p>
                </div>
            )}

            {/* Keywords */}
            {result.keywords && result.keywords.length > 0 && (
                <div className="mb-4">
                    <h4 className="text-sm font-semibold text-gray-600 mb-2">Keywords</h4>
                    <div className="flex flex-wrap gap-2">
                        {result.keywords.map((keyword, idx) => (
                            <span 
                                key={idx}
                                className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm"
                            >
                                {keyword}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Healthiness Score */}
            {healthinessScore !== undefined && healthinessScore !== null && (
                <div className="mb-4 p-4 bg-gradient-to-r from-blue-50 to-green-50 rounded-lg">
                    <h4 className="text-sm font-semibold text-gray-600 mb-1">Healthiness Score</h4>
                    <div className="text-3xl font-bold text-blue-600">{healthinessScore} / 10</div>
                </div>
            )}

            {/* Rationale */}
            {rationale && (
                <div className="mb-4">
                    <h4 className="text-sm font-semibold text-gray-600 mb-1">Rationale</h4>
                    <p className="text-gray-700 text-sm">{rationale}</p>
                </div>
            )}

            {/* Macronutrients */}
            {result.macronutrients && (
                <div className="mb-4">
                    <h4 className="text-sm font-semibold text-gray-600 mb-2">Macronutrients</h4>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                        <div className="p-2 bg-gray-50 rounded">
                            <span className="text-gray-600">Calories:</span>
                            <span className="font-medium ml-2">{result.macronutrients.calories || 'N/A'}</span>
                        </div>
                        <div className="p-2 bg-gray-50 rounded">
                            <span className="text-gray-600">Protein:</span>
                            <span className="font-medium ml-2">{result.macronutrients.protein || 'N/A'}g</span>
                        </div>
                        <div className="p-2 bg-gray-50 rounded">
                            <span className="text-gray-600">Carbs:</span>
                            <span className="font-medium ml-2">{result.macronutrients.carbohydrates || 'N/A'}g</span>
                        </div>
                        <div className="p-2 bg-gray-50 rounded">
                            <span className="text-gray-600">Fat:</span>
                            <span className="font-medium ml-2">{result.macronutrients.fat || 'N/A'}g</span>
                        </div>
                    </div>
                </div>
            )}

            {/* Micronutrients */}
            {result.micronutrients && result.micronutrients.length > 0 && (
                <div className="mb-4">
                    <h4 className="text-sm font-semibold text-gray-600 mb-2">Key Micronutrients</h4>
                    <div className="space-y-1">
                        {result.micronutrients.slice(0, 5).map((micro, idx) => (
                            <div key={idx} className="text-sm text-gray-700">
                                • {micro.nutrient}: {micro.amount_per_serving} ({micro.percentage_dv}% DV)
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export const AnalysisResults = ({ item }) => {
    return (
        <div className="mt-8">
            <h2 className="text-2xl font-bold text-gray-800 mb-6">Analysis Results</h2>
            
            {/* Two-column layout */}
            <div className="flex flex-col md:flex-row gap-6">
                <AnalysisColumn 
                    title="OpenAI Analysis" 
                    result={item.result_openai}
                    colorClass="text-green-600"
                />
                <AnalysisColumn 
                    title="Gemini Analysis" 
                    result={item.result_gemini}
                    colorClass="text-blue-600"
                />
            </div>
        </div>
    );
};

