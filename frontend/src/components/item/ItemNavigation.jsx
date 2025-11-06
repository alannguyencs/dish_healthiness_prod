import React from 'react';

export const ItemNavigation = ({ onBackToDate }) => {
    return (
        <div className="flex items-center justify-between mb-6">
            <button
                onClick={onBackToDate}
                className="flex items-center space-x-2 px-4 py-2 bg-gray-100 
                           text-gray-700 rounded-lg hover:bg-gray-200 
                           transition-colors duration-200"
            >
                <svg 
                    className="w-5 h-5" 
                    fill="none" 
                    stroke="currentColor" 
                    viewBox="0 0 24 24"
                >
                    <path 
                        strokeLinecap="round" 
                        strokeLinejoin="round" 
                        strokeWidth={2} 
                        d="M10 19l-7-7m0 0l7-7m-7 7h18" 
                    />
                </svg>
                <span>Back to Date View</span>
            </button>
        </div>
    );
};

