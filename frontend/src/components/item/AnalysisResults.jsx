import React from 'react';

const getHealthinessBadge = (score) => {
    if (!score && score !== 0) return { text: '-', className: 'bg-gray-100 text-gray-600' };
    
    if (score >= 7) {
        return { text: 'HEALTHY', className: 'bg-green-100 text-green-800 border-green-300' };
    } else if (score >= 4) {
        return { text: 'NEUTRAL', className: 'bg-gray-200 text-gray-700 border-gray-400' };
    } else {
        return { text: 'UNHEALTHY', className: 'bg-orange-100 text-orange-700 border-orange-400' };
    }
};

const Rationale = ({ text }) => {
    if (!text) return <span className="text-gray-400">-</span>;
    
    return (
        <div>
            <p className="text-sm text-gray-700 whitespace-pre-wrap">{text}</p>
        </div>
    );
};

const TableCell = ({ children, isHeader, openaiTheme, geminiTheme }) => {
    const baseClasses = "px-4 py-3 border-r border-gray-300";
    
    if (isHeader) {
        if (openaiTheme) {
            return (
                <th className={`${baseClasses} bg-green-600 text-white font-semibold text-center`}>
                    <div className="flex items-center justify-center">
                        <span className="mr-2">🔮</span>
                        {children}
                    </div>
                </th>
            );
        }
        if (geminiTheme) {
            return (
                <th className={`${baseClasses} bg-blue-600 text-white font-semibold text-center`}>
                    <div className="flex items-center justify-center">
                        <span className="mr-2">💎</span>
                        {children}
                    </div>
                </th>
            );
        }
        return <th className={`${baseClasses} bg-gray-700 text-white font-semibold`}>{children}</th>;
    }
    
    return <td className={`${baseClasses} text-sm`}>{children}</td>;
};

const TableRow = ({ label, openaiValue, geminiValue, icon, altBg }) => {
    const rowClass = altBg ? "bg-gray-50" : "bg-white";
    
    return (
        <tr className={rowClass}>
            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                <div className="flex items-center">
                    {icon && <span className="mr-2">{icon}</span>}
                    {label}
                </div>
            </td>
            <TableCell>{openaiValue}</TableCell>
            <TableCell>{geminiValue}</TableCell>
        </tr>
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
    const openaiResult = item.result_openai || {};
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
                            <th className="px-4 py-3 bg-gray-700 text-white font-semibold text-left border-r border-gray-300 w-1/4">
                                Analysis Category
                            </th>
                            <TableCell isHeader openaiTheme>OpenAI</TableCell>
                            <TableCell isHeader geminiTheme>Gemini</TableCell>
                        </tr>
                    </thead>
                    
                    <tbody className="divide-y divide-gray-300">
                        {/* Model */}
                        <TableRow
                            label="🤖 Model"
                            openaiValue={formatModelName(openaiResult.model)}
                            geminiValue={formatModelName(geminiResult.model)}
                        />
                        
                        {/* Input Tokens */}
                        <TableRow
                            label="📥 Input tokens"
                            openaiValue={formatValue(openaiResult.input_token)}
                            geminiValue={formatValue(geminiResult.input_token)}
                            altBg
                        />
                        
                        {/* Output Tokens */}
                        <TableRow
                            label="📤 Output tokens"
                            openaiValue={formatValue(openaiResult.output_token)}
                            geminiValue={formatValue(geminiResult.output_token)}
                        />
                        
                        {/* Cost */}
                        <TableRow
                            label="💰 Cost"
                            openaiValue={formatCurrency(openaiResult.price_usd)}
                            geminiValue={formatCurrency(geminiResult.price_usd)}
                            altBg
                        />
                        
                        {/* Analysis Time */}
                        <TableRow
                            label="⏱️ Analysis Time"
                            openaiValue={formatValue(openaiResult.analysis_time, 's')}
                            geminiValue={formatValue(geminiResult.analysis_time, 's')}
                        />
                        
                        {/* Dish Name */}
                        <TableRow
                            label="🍽️ Dish Name"
                            openaiValue={formatValue(openaiResult.dish_name)}
                            geminiValue={formatValue(geminiResult.dish_name)}
                            altBg
                        />
                        
                        {/* Healthiness */}
                        <tr className="bg-white">
                            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                                ⭐ Healthiness
                            </td>
                            <TableCell>
                                {openaiResult.healthiness_score !== undefined && openaiResult.healthiness_score !== null ? (
                                    <span className={`inline-block px-3 py-1 rounded-full text-sm font-bold border ${getHealthinessBadge(openaiResult.healthiness_score).className}`}>
                                        {getHealthinessBadge(openaiResult.healthiness_score).text}
                                    </span>
                                ) : (
                                    <span className="text-gray-400">-</span>
                                )}
                            </TableCell>
                            <TableCell>
                                {geminiResult.healthiness_score !== undefined && geminiResult.healthiness_score !== null ? (
                                    <span className={`inline-block px-3 py-1 rounded-full text-sm font-bold border ${getHealthinessBadge(geminiResult.healthiness_score).className}`}>
                                        {getHealthinessBadge(geminiResult.healthiness_score).text}
                                    </span>
                                ) : (
                                    <span className="text-gray-400">-</span>
                                )}
                            </TableCell>
                        </tr>
                        
                        {/* Healthiness Rationale */}
                        <tr className="bg-gray-50">
                            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                                🔍 Healthiness Rationale
                            </td>
                            <TableCell>
                                <Rationale text={openaiResult.healthiness_score_rationale} />
                            </TableCell>
                            <TableCell>
                                <Rationale text={geminiResult.healthiness_score_rationale} />
                            </TableCell>
                        </tr>
                        
                        {/* Calories */}
                        <TableRow
                            label="🔥 Calories (kcal)"
                            openaiValue={formatValue(openaiResult.calories_kcal)}
                            geminiValue={formatValue(geminiResult.calories_kcal)}
                            altBg
                        />
                        
                        {/* Fiber */}
                        <TableRow
                            label="🌾 Fiber (g)"
                            openaiValue={formatValue(openaiResult.fiber_g)}
                            geminiValue={formatValue(geminiResult.fiber_g)}
                        />
                        
                        {/* Carbs */}
                        <TableRow
                            label="🍞 Carbs (g)"
                            openaiValue={formatValue(openaiResult.carbs_g)}
                            geminiValue={formatValue(geminiResult.carbs_g)}
                            altBg
                        />
                        
                        {/* Protein */}
                        <TableRow
                            label="🥩 Protein (g)"
                            openaiValue={formatValue(openaiResult.protein_g)}
                            geminiValue={formatValue(geminiResult.protein_g)}
                        />
                        
                        {/* Fat */}
                        <TableRow
                            label="🧈 Fat (g)"
                            openaiValue={formatValue(openaiResult.fat_g)}
                            geminiValue={formatValue(geminiResult.fat_g)}
                            altBg
                        />
                        
                        {/* Micronutrients */}
                        <tr className="bg-white">
                            <td className="px-4 py-3 border-r border-gray-300 font-medium text-gray-700 bg-gray-100">
                                🍊 Micronutrients
                            </td>
                            <TableCell>{formatMicronutrients(openaiResult.micronutrients)}</TableCell>
                            <TableCell>{formatMicronutrients(geminiResult.micronutrients)}</TableCell>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    );
};
