import React from "react";

export const NoAnalysisAvailable = () => {
  return (
    <div className="mt-8 p-8 bg-gray-50 rounded-lg border border-gray-200">
      <p className="text-center text-gray-600">
        No analysis results available for this dish yet.
      </p>
    </div>
  );
};
