import React from "react";

/**
 * DishNameSelector Component
 *
 * Allows user to select from AI-predicted dish names or enter a custom name.
 */
const DishNameSelector = ({
  dishPredictions,
  selectedDishName,
  customDishName,
  useCustomDish,
  showAllPredictions,
  onSelectDish,
  onCustomDishChange,
  onUseCustomToggle,
  onToggleShowAll,
}) => {
  return (
    <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
      <h3 className="text-lg font-semibold text-gray-800 mb-4">
        Overall Meal Name
      </h3>

      {/* Top prediction with dropdown toggle */}
      <div className="flex items-center gap-2 mb-2">
        <label className="flex items-center gap-2 flex-1">
          <input
            type="radio"
            name="dish_name"
            checked={
              !useCustomDish && selectedDishName === dishPredictions[0]?.name
            }
            onChange={() => {
              onUseCustomToggle(false);
              onSelectDish(dishPredictions[0]?.name);
            }}
            className="w-4 h-4"
          />
          <span className="font-medium">{dishPredictions[0]?.name}</span>
          {dishPredictions[0]?.confidence && (
            <span className="text-xs text-gray-500">
              ({(dishPredictions[0].confidence * 100).toFixed(0)}%)
            </span>
          )}
        </label>

        {/* Dropdown toggle */}
        {dishPredictions.length > 1 && (
          <button
            type="button"
            onClick={onToggleShowAll}
            className="text-blue-600 hover:text-blue-700 p-1"
            aria-label={
              showAllPredictions ? "Hide predictions" : "Show more predictions"
            }
          >
            {showAllPredictions ? (
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
                  d="M5 15l7-7 7 7"
                />
              </svg>
            ) : (
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
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            )}
          </button>
        )}
      </div>

      {/* Remaining predictions (collapsible) */}
      {showAllPredictions &&
        dishPredictions.slice(1).map((pred) => (
          <label key={pred.name} className="flex items-center gap-2 mb-2 ml-6">
            <input
              type="radio"
              name="dish_name"
              checked={!useCustomDish && selectedDishName === pred.name}
              onChange={() => {
                onUseCustomToggle(false);
                onSelectDish(pred.name);
              }}
              className="w-4 h-4"
            />
            <span className="font-medium">{pred.name}</span>
            {pred.confidence && (
              <span className="text-xs text-gray-500">
                ({(pred.confidence * 100).toFixed(0)}%)
              </span>
            )}
          </label>
        ))}

      {/* Custom dish name option */}
      <div className="mt-4 border-t border-gray-200 pt-4">
        <label className="flex items-start gap-2">
          <input
            type="radio"
            name="dish_name"
            checked={useCustomDish}
            onChange={() => onUseCustomToggle(true)}
            className="w-4 h-4 mt-1"
          />
          <div className="flex-1">
            <span className="font-medium block mb-2">Custom Dish Name</span>
            <input
              type="text"
              value={customDishName}
              onChange={(e) => onCustomDishChange(e.target.value)}
              placeholder="Enter custom dish name"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              disabled={!useCustomDish}
            />
          </div>
        </label>
      </div>
    </div>
  );
};

export default DishNameSelector;
