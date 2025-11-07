import React from 'react';

export const AnalysisLoading = () => {
    return (
        <div className="mt-8 p-8 bg-blue-50 rounded-lg border border-blue-200">
            <div className="flex flex-col items-center justify-center space-y-3">
                <div className="flex items-center space-x-3">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                    <div className="text-lg text-blue-700">
                        Analysis in progress... This may take a moment.
                    </div>
                </div>
                <div className="text-sm text-blue-600">
                    Processing normally takes 20-30 seconds.
                </div>
            </div>
        </div>
    );
};

