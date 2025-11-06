import React from 'react';
import { MealUploadSlot } from './MealUploadSlot';

export const MealUploadGrid = ({ dateData, uploading, onFileUpload }) => {
    return (
        <div>
            <h2 className="text-2xl font-bold text-gray-800 mb-6">
                {dateData.formatted_date}
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {dateData.meal_types.map((mealType) => (
                    <MealUploadSlot
                        key={mealType}
                        mealType={mealType}
                        mealData={dateData.meal_data[mealType]}
                        uploading={uploading}
                        onFileUpload={onFileUpload}
                    />
                ))}
            </div>
            
            {dateData.meal_types.some(mt => dateData.meal_data[mt].has_data) && (
                <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                    <p className="text-sm text-blue-800">
                        💡 Click on any uploaded meal image to view its detailed analysis.
                    </p>
                </div>
            )}
        </div>
    );
};

