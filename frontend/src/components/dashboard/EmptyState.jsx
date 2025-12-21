import React from "react";

/**
 * Empty State Component
 *
 * Displays a message when there's no analysis history.
 */
const EmptyState = () => {
  return (
    <div className="text-center mt-8 p-8 bg-gray-100 rounded-lg border-2 border-dashed border-gray-300">
      <div className="text-6xl mb-4">📅</div>
      <h3 className="text-xl font-bold text-gray-700 mb-2">No Dishes Yet</h3>
      <p className="text-gray-600">
        You haven't uploaded any dish images yet. Click on a date to start!
      </p>
    </div>
  );
};

export default EmptyState;
