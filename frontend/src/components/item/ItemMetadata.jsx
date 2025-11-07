import React from 'react';

export const ItemMetadata = ({ item, getHealthinessLabel }) => {
    return (
        <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-700">
                Record Information
            </h3>
            
            <div className="space-y-3">
                <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                    <span className="text-gray-600">Dish Position:</span>
                    <span className="font-medium">
                        {item.dish_position ? `Dish ${item.dish_position}` : 'N/A'}
                    </span>
                </div>
                
                <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                    <span className="text-gray-600">Created At:</span>
                    <span className="font-medium">
                        {item.created_at ? new Date(item.created_at).toLocaleString() : 'N/A'}
                    </span>
                </div>
                
                <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
                    <span className="text-gray-600">Target Date:</span>
                    <span className="font-medium">
                        {item.target_date ? new Date(item.target_date).toLocaleDateString() : 'N/A'}
                    </span>
                </div>
            </div>
        </div>
    );
};

