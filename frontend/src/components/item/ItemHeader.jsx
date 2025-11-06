import React from 'react';

export const ItemHeader = ({ itemId }) => {
    return (
        <div className="border-b pb-4 mb-6">
            <h1 className="text-3xl font-bold text-gray-800">
                Dish Analysis Details
            </h1>
            <p className="text-sm text-gray-500 mt-1">
                Record ID: {itemId}
            </p>
        </div>
    );
};

