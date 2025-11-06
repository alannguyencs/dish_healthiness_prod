import React from 'react';

/**
 * Month Navigation Component
 *
 * Displays month/year and navigation buttons.
 */
const MonthNavigation = ({
    monthName,
    displayYear,
    onPrevious,
    onNext
}) => {
    return (
        <div className="flex justify-between items-center mb-6 p-4 bg-gray-100 rounded-lg">
            <button
                onClick={onPrevious}
                className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded font-bold transition"
            >
                ← Previous
            </button>
            <div className="text-2xl font-bold text-gray-800">
                {monthName} {displayYear}
            </div>
            <button
                onClick={onNext}
                className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded font-bold transition"
            >
                Next →
            </button>
        </div>
    );
};

export default MonthNavigation;

