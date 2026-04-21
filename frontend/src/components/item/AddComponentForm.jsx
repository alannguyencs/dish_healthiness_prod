import React from "react";

/**
 * AddComponentForm Component
 *
 * Form for adding custom components manually.
 */
const AddComponentForm = ({
  componentName,
  servingSize,
  numberOfServings,
  onComponentNameChange,
  onServingSizeChange,
  onServingsChange,
  onAdd,
  onCancel,
}) => {
  return (
    <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
      <h4 className="font-semibold text-gray-800 mb-3">Add Component</h4>

      <div className="space-y-3">
        {/* Component name input */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Component Name
          </label>
          <input
            type="text"
            value={componentName}
            onChange={(e) => onComponentNameChange(e.target.value)}
            placeholder="e.g., Grilled Chicken Breast"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Serving size input */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Serving Size
          </label>
          <input
            type="text"
            value={servingSize}
            onChange={(e) => onServingSizeChange(e.target.value)}
            placeholder="e.g., 1 piece (85g)"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Number of servings input */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Number of Servings
          </label>
          <input
            type="number"
            min="0.1"
            max="10"
            step="0.1"
            value={numberOfServings}
            onChange={(e) => onServingsChange(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Action buttons */}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onAdd}
            className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 font-medium"
          >
            Add Component
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 text-gray-600 hover:text-gray-800 font-medium"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

export default AddComponentForm;
