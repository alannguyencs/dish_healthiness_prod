import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';

// TODO: Implement Item page
// Reference: /Volumes/wd/projects/food_healthiness_product/frontend/src/pages/Item.jsx
// Simplify to show only 2 columns: OpenAI (Flow 2) and Gemini (Flow 3)

const Item = () => {
    const { recordId } = useParams();
    const navigate = useNavigate();

    return (
        <div className="min-h-screen bg-gray-100">
            <div className="bg-white shadow">
                <div className="max-w-7xl mx-auto px-4 py-4">
                    <button
                        onClick={() => navigate(-1)}
                        className="text-blue-600 hover:underline"
                    >
                        ← Back
                    </button>
                    <h1 className="text-2xl font-bold mt-2">
                        Item Details: {recordId}
                    </h1>
                </div>
            </div>
            
            <div className="max-w-7xl mx-auto px-4 py-8">
                <div className="bg-yellow-100 border border-yellow-400 text-yellow-800 px-4 py-3 rounded">
                    <p className="font-bold">TODO: Implement Item Page</p>
                    <p className="mt-2">
                        Copy from: /Volumes/wd/projects/food_healthiness_product/frontend/src/pages/Item.jsx
                    </p>
                    <p className="mt-1">
                        Show only 2 analysis columns:
                    </p>
                    <ul className="list-disc list-inside ml-4 mt-1">
                        <li>Column 1: OpenAI (Flow 2) - result_openai</li>
                        <li>Column 2: Gemini (Flow 3) - result_gemini</li>
                    </ul>
                    <p className="mt-1">
                        Display fields: dish_name, healthiness_score, healthiness_score_rationale,
                        calories_kcal, carbs_g, protein_g, fat_g, fiber_g, related_keywords, micronutrients
                    </p>
                </div>
            </div>
        </div>
    );
};

export default Item;

