import React from 'react';

const getHealthinessBadge = (score) => {
    if (!score && score !== 0) return { text: '-', className: 'bg-gray-100 text-gray-600' };
    
    if (score >= 9) {
        return { text: 'VERY HIGH', className: 'bg-green-600 text-white border-green-700' };
    } else if (score >= 7) {
        return { text: 'HIGH', className: 'bg-green-100 text-green-800 border-green-300' };
    } else if (score >= 5) {
        return { text: 'MEDIUM', className: 'bg-yellow-100 text-yellow-800 border-yellow-400' };
    } else if (score >= 3) {
        return { text: 'LOW', className: 'bg-orange-100 text-orange-700 border-orange-400' };
    } else {
        return { text: 'VERY LOW', className: 'bg-red-100 text-red-800 border-red-400' };
    }
};

const Rationale = ({ text }) => {
    if (!text) return <span className="text-gray-400">-</span>;
    
    return (
        <div>
            <p className="text-sm text-gray-700 whitespace-pre-wrap text-justify">{text}</p>
        </div>
    );
};

const formatModelName = (modelName) => {
    if (!modelName) return '-';
    
    // Map technical model names to user-friendly display names
    const modelMap = {
        'gpt-5-low': 'gpt-5-low',
        'gpt-5-2025-08-07': 'gpt-5-low',
        'gemini-2.5-flash': 'gemini-2.5-pro',
        'gemini-2.5-pro': 'gemini-2.5-pro'
    };
    
    return modelMap[modelName] || modelName;
};

export const AnalysisResults = ({ item }) => {
    const geminiResult = item.result_gemini || {};

    // Format values with fallbacks
    const formatValue = (value, suffix = '') => {
        if (value === null || value === undefined) return '-';
        return `${value}${suffix}`;
    };

    const formatCurrency = (value) => {
        if (value === null || value === undefined) return '-';
        return `$${parseFloat(value).toFixed(4)}`;
    };

    const formatMicronutrients = (micronutrients) => {
        if (!micronutrients || micronutrients.length === 0) {
            return <span className="text-gray-400">-</span>;
        }

        return (
            <div className="flex flex-wrap gap-1">
                {micronutrients.map((nutrient, idx) => (
                    <span
                        key={idx}
                        className="px-2 py-1 bg-purple-100 text-purple-800 rounded-full text-xs"
                    >
                        {nutrient}
                    </span>
                ))}
            </div>
        );
    };

    return (
        <div className="mt-8">
            <h2 className="text-2xl font-bold text-gray-800 mb-6">Analysis Results</h2>

            <div className="overflow-x-auto shadow-lg rounded-lg border border-gray-300">
                <table className="w-full border-collapse">
                    {/* Header Row */}
                    <thead>
                        <tr>
                            <th className="px-4 py-3 bg-gray-700 text-white font-semibold text-left border-r border-gray-300 w-1/3">
                                Analysis Category
                            </th>
                            <th className="px-4 py-3 bg-blue-600 text-white font-semibold text-center">
                                <div className="flex items-center justify-center">
                                    <span className="mr-2">💎</span>
                                    Gemini
                                </div>
                            </th>
                        </tr>
                    </thead>

                    <tbody className="divide-y divide-gray-300">
                        {/* Model */}
                        <tr className="bg-white">
                            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                                🤖 Model
                            </td>
                            <td className="px-4 py-3 text-sm text-center">{formatModelName(geminiResult.model)}</td>
                        </tr>

                        {/* Input Tokens */}
                        <tr className="bg-gray-50">
                            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                                📥 Input tokens
                            </td>
                            <td className="px-4 py-3 text-sm text-center">{formatValue(geminiResult.input_token)}</td>
                        </tr>

                        {/* Output Tokens */}
                        <tr className="bg-white">
                            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                                📤 Output tokens
                            </td>
                            <td className="px-4 py-3 text-sm text-center">{formatValue(geminiResult.output_token)}</td>
                        </tr>

                        {/* Cost */}
                        <tr className="bg-gray-50">
                            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                                💰 Cost
                            </td>
                            <td className="px-4 py-3 text-sm text-center">{formatCurrency(geminiResult.price_usd)}</td>
                        </tr>

                        {/* Analysis Time */}
                        <tr className="bg-white">
                            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                                ⏱️ Analysis Time
                            </td>
                            <td className="px-4 py-3 text-sm text-center">{formatValue(geminiResult.analysis_time, 's')}</td>
                        </tr>

                        {/* Dish Name */}
                        <tr className="bg-gray-50">
                            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                                🍽️ Dish Name
                            </td>
                            <td className="px-4 py-3 text-sm text-center">{formatValue(geminiResult.dish_name)}</td>
                        </tr>

                        {/* Healthiness */}
                        <tr className="bg-white">
                            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                                ⭐ Healthiness
                            </td>
                            <td className="px-4 py-3 text-sm text-center">
                                {geminiResult.healthiness_score !== undefined && geminiResult.healthiness_score !== null ? (
                                    <span className={`inline-block px-3 py-1 rounded-full text-sm font-bold border ${getHealthinessBadge(geminiResult.healthiness_score).className}`}>
                                        {getHealthinessBadge(geminiResult.healthiness_score).text}
                                    </span>
                                ) : (
                                    <span className="text-gray-400">-</span>
                                )}
                            </td>
                        </tr>

                        {/* Healthiness Rationale */}
                        <tr className="bg-gray-50">
                            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                                🔍 Healthiness Rationale
                            </td>
                            <td className="px-4 py-3 text-sm">
                                <Rationale text={geminiResult.healthiness_score_rationale} />
                            </td>
                        </tr>

                        {/* Calories */}
                        <tr className="bg-white">
                            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                                🔥 Calories (kcal)
                            </td>
                            <td className="px-4 py-3 text-sm text-center">{formatValue(geminiResult.calories_kcal)}</td>
                        </tr>

                        {/* Fiber */}
                        <tr className="bg-gray-50">
                            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                                🌾 Fiber (g)
                            </td>
                            <td className="px-4 py-3 text-sm text-center">{formatValue(geminiResult.fiber_g)}</td>
                        </tr>

                        {/* Carbs */}
                        <tr className="bg-white">
                            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                                🍞 Carbs (g)
                            </td>
                            <td className="px-4 py-3 text-sm text-center">{formatValue(geminiResult.carbs_g)}</td>
                        </tr>

                        {/* Protein */}
                        <tr className="bg-gray-50">
                            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                                🥩 Protein (g)
                            </td>
                            <td className="px-4 py-3 text-sm text-center">{formatValue(geminiResult.protein_g)}</td>
                        </tr>

                        {/* Fat */}
                        <tr className="bg-white">
                            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                                🧈 Fat (g)
                            </td>
                            <td className="px-4 py-3 text-sm text-center">{formatValue(geminiResult.fat_g)}</td>
                        </tr>

                        {/* Micronutrients */}
                        <tr className="bg-gray-50">
                            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                                🍊 Micronutrients
                            </td>
                            <td className="px-4 py-3 text-sm">{formatMicronutrients(geminiResult.micronutrients)}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    );
};
