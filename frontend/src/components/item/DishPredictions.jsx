import React, { useState, useEffect, useRef } from "react";

/**
 * DishPredictions Component
 *
 * Dropdown selector for AI-generated dish predictions with custom input capability.
 * Shows top 5 predictions with confidence scores and allows user override.
 */
const DishPredictions = ({
  predictions = [],
  selectedDish,
  onDishSelect,
  disabled = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [customInput, setCustomInput] = useState("");
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () =>
        document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isOpen]);

  // Auto-select top prediction on initial load
  useEffect(() => {
    if (predictions.length > 0 && !selectedDish) {
      onDishSelect(predictions[0].name);
    }
  }, [predictions, selectedDish, onDishSelect]);

  const handleDishClick = (dishName) => {
    onDishSelect(dishName);
    setIsOpen(false);
  };

  const handleCustomSubmit = (e) => {
    e.preventDefault();
    if (customInput.trim()) {
      onDishSelect(customInput.trim());
      setCustomInput("");
      setIsOpen(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Escape") {
      setIsOpen(false);
    }
  };

  if (!predictions || predictions.length === 0) {
    return (
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Dish Name
        </label>
        <input
          type="text"
          value={selectedDish || ""}
          onChange={(e) => onDishSelect(e.target.value)}
          placeholder="Enter dish name"
          disabled={disabled}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
        />
        <p className="mt-1 text-sm text-gray-500">
          No dish predictions available
        </p>
      </div>
    );
  }

  const topPrediction = predictions[0];
  const isTopChoice = selectedDish === topPrediction.name;
  const isCustom =
    selectedDish && !predictions.find((p) => p.name === selectedDish);
  const selectedPrediction = predictions.find((p) => p.name === selectedDish);

  return (
    <div className="mb-4 relative" ref={dropdownRef}>
      <label className="block text-sm font-medium text-gray-700 mb-2">
        Dish Identification
      </label>

      {/* Dropdown Trigger - Compact View */}
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        onKeyDown={handleKeyDown}
        className="w-full bg-white border-2 border-blue-300 rounded-lg px-4 py-2.5 text-left focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 hover:bg-gray-50 transition-colors"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        <div className="flex items-center justify-between">
          <div className="flex-1 min-w-0">
            <div className="font-medium text-gray-900 truncate">
              {selectedDish || "Select a dish"}
            </div>
            {selectedPrediction && (
              <div className="text-xs text-gray-500 mt-0.5">
                Confidence: {Math.round(selectedPrediction.confidence * 100)}%
              </div>
            )}
          </div>
          <div className="flex items-center gap-2 ml-3 flex-shrink-0">
            {isTopChoice && (
              <span className="px-2 py-0.5 bg-green-100 text-green-800 text-xs font-semibold rounded">
                TOP
              </span>
            )}
            {!isTopChoice && !isCustom && selectedPrediction && (
              <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-xs font-semibold rounded">
                User Selected
              </span>
            )}
            {isCustom && (
              <span className="px-2 py-0.5 bg-purple-100 text-purple-800 text-xs font-semibold rounded">
                Custom
              </span>
            )}
            <svg
              className={`w-4 h-4 text-gray-500 transition-transform ${isOpen ? "rotate-180" : ""}`}
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
          </div>
        </div>
      </button>

      {/* Compact Selection Note */}
      {!isTopChoice && selectedDish && (
        <p className="mt-1.5 text-xs text-gray-600">
          AI suggested:{" "}
          <span className="font-medium">{topPrediction.name}</span> (
          {Math.round(topPrediction.confidence * 100)}%)
        </p>
      )}

      {/* Dropdown Menu - Overlays content below */}
      {isOpen && (
        <div className="absolute z-50 mt-1 w-full bg-white border border-gray-300 rounded-lg shadow-xl max-h-80 overflow-y-auto">
          {/* AI Predictions List - Compact */}
          <div className="p-1.5">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide px-2 py-1.5">
              AI Predictions
            </div>
            {predictions.map((prediction, index) => (
              <button
                key={index}
                type="button"
                onClick={() => handleDishClick(prediction.name)}
                className="w-full text-left px-2 py-2 hover:bg-blue-50 rounded transition-colors"
                role="option"
                aria-selected={selectedDish === prediction.name}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-semibold text-gray-400">
                        #{index + 1}
                      </span>
                      <span className="text-sm font-medium text-gray-900 truncate">
                        {prediction.name}
                      </span>
                      {index === 0 && (
                        <span className="px-1.5 py-0.5 bg-green-100 text-green-700 text-xs font-semibold rounded">
                          TOP
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex items-center gap-1.5">
                      <div className="flex-1 bg-gray-200 rounded-full h-1.5">
                        <div
                          className="bg-blue-500 h-1.5 rounded-full transition-all"
                          style={{ width: `${prediction.confidence * 100}%` }}
                        />
                      </div>
                      <span className="text-xs font-medium text-gray-600 whitespace-nowrap">
                        {Math.round(prediction.confidence * 100)}%
                      </span>
                    </div>
                  </div>
                  {selectedDish === prediction.name && (
                    <svg
                      className="w-4 h-4 text-blue-600 flex-shrink-0"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  )}
                </div>
              </button>
            ))}
          </div>

          {/* Custom Input Section - Compact */}
          <div className="border-t border-gray-200 p-2 bg-gray-50">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
              Custom Dish
            </div>
            <form onSubmit={handleCustomSubmit} className="flex gap-1.5">
              <input
                type="text"
                value={customInput}
                onChange={(e) => setCustomInput(e.target.value)}
                placeholder="Enter dish name"
                className="flex-1 px-2.5 py-1.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <button
                type="submit"
                disabled={!customInput.trim()}
                className="px-3 py-1.5 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                Add
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default DishPredictions;
