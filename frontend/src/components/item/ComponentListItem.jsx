import React from "react";

/**
 * ComponentListItem Component
 *
 * Displays a single component (AI-predicted or manual) with editing controls.
 */
const ComponentListItem = ({
  componentName,
  servingSize,
  numberOfServings,
  servingSizeOptions = [],
  enabled = true,
  isManual = false,
  onToggle,
  onServingSizeChange,
  onServingsChange,
  onRemove,
}) => {
  return (
    <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
      {/* Component header with checkbox/remove button */}
      <div className="flex items-center gap-3 mb-3">
        {!isManual ? (
          <input
            type="checkbox"
            checked={enabled}
            onChange={() => onToggle && onToggle(componentName)}
            className="w-5 h-5 text-blue-600"
          />
        ) : null}

        <h4
          className={`flex-1 font-semibold ${
            !isManual && !enabled
              ? "text-gray-400 line-through"
              : "text-gray-800"
          }`}
        >
          {componentName}
          {isManual && (
            <span className="ml-2 text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded">
              Manual
            </span>
          )}
        </h4>

        {isManual && onRemove && (
          <button
            type="button"
            onClick={() => onRemove(componentName)}
            className="text-red-600 hover:text-red-700 text-sm font-medium"
          >
            Remove
          </button>
        )}
      </div>

      {/* Serving details (only show if enabled or manual) */}
      {(enabled || isManual) && (
        <div className="grid grid-cols-[110px_minmax(200px,1fr)_160px_80px] gap-3 items-center text-sm">
          <span className="text-gray-700 font-medium">Serving Size:</span>

          {servingSizeOptions.length > 0 ? (
            <select
              value={servingSize}
              onChange={(e) =>
                onServingSizeChange &&
                onServingSizeChange(componentName, e.target.value)
              }
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              {servingSizeOptions.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              value={servingSize}
              onChange={(e) =>
                onServingSizeChange &&
                onServingSizeChange(componentName, e.target.value)
              }
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="e.g., 1 cup (100g)"
            />
          )}

          <span className="text-gray-700 font-medium">Number of Servings:</span>

          <input
            type="number"
            min="0.1"
            max="10"
            step="0.1"
            value={numberOfServings}
            onChange={(e) =>
              onServingsChange &&
              onServingsChange(componentName, e.target.value)
            }
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>
      )}
    </div>
  );
};

export default ComponentListItem;
