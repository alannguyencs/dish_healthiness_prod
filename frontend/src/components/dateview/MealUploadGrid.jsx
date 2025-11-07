import React from 'react';
import { MealUploadSlot } from './MealUploadSlot';

export const MealUploadGrid = ({ dateData, uploading, onFileUpload }) => {
    const maxDishes = dateData.max_dishes || 5;
    const dishPositions = Array.from({ length: maxDishes }, (_, i) => i + 1);
    
    return (
        <div>
            <h2 className="text-2xl font-bold text-gray-800 mb-6">
                {dateData.formatted_date}
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
                {dishPositions.map((position) => (
                    <MealUploadSlot
                        key={position}
                        dishPosition={position}
                        dishData={dateData.dish_data[`dish_${position}`]}
                        uploading={uploading}
                        onFileUpload={onFileUpload}
                    />
                ))}
            </div>
            
            {Object.values(dateData.dish_data || {}).some(d => d.has_data) && (
                <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                    <p className="text-sm text-blue-800">
                        💡 Click on any uploaded dish image to view its detailed analysis.
                    </p>
                </div>
            )}
        </div>
    );
};

