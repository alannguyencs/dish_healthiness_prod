import React, { useState, useEffect } from "react";

/**
 * ServingsCountInput Component
 *
 * Number input with increment/decrement controls for specifying servings consumed.
 * Validates minimum (0.1) and rounds to 1 decimal place. No maximum limit.
 * Shows AI prediction badge when available.
 */
const ServingsCountInput = ({
  value = 1.0,
  onChange,
  disabled = false,
  min = 0.1,
  max = null, // No maximum limit
  step = 0.5,
  predictedServings = null, // AI predicted number of servings
}) => {
  const [inputValue, setInputValue] = useState(value.toString());

  // Sync with prop changes
  useEffect(() => {
    setInputValue(value.toString());
  }, [value]);

  const handleIncrement = () => {
    const newValue = max !== null ? Math.min(max, value + step) : value + step;
    const rounded = Math.round(newValue * 10) / 10;
    onChange(rounded);
  };

  const handleDecrement = () => {
    const newValue = Math.max(min, value - step);
    const rounded = Math.round(newValue * 10) / 10;
    onChange(rounded);
  };

  const handleInputChange = (e) => {
    setInputValue(e.target.value);
  };

  const handleInputBlur = () => {
    const numValue = parseFloat(inputValue);

    if (isNaN(numValue) || numValue < min) {
      setInputValue(min.toString());
      onChange(min);
    } else if (max !== null && numValue > max) {
      setInputValue(max.toString());
      onChange(max);
    } else {
      const rounded = Math.round(numValue * 10) / 10;
      setInputValue(rounded.toString());
      onChange(rounded);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "ArrowUp") {
      e.preventDefault();
      handleIncrement();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      handleDecrement();
    } else if (e.key === "Enter") {
      e.target.blur();
    }
  };

  const isUsingPrediction =
    predictedServings !== null && Math.abs(value - predictedServings) < 0.01;

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-2">
        <label className="block text-sm font-medium text-gray-700">
          Number of Servings
        </label>
        {predictedServings !== null && isUsingPrediction && (
          <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs font-semibold rounded">
            AI Estimate
          </span>
        )}
      </div>

      <div className="flex items-center gap-3">
        {/* Decrement Button */}
        <button
          type="button"
          onClick={handleDecrement}
          disabled={disabled || value <= min}
          className="w-10 h-10 flex items-center justify-center bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:bg-gray-100 disabled:cursor-not-allowed transition-colors"
          aria-label="Decrease servings"
        >
          <svg
            className="w-5 h-5 text-gray-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M20 12H4"
            />
          </svg>
        </button>

        {/* Number Input */}
        <input
          type="number"
          value={inputValue}
          onChange={handleInputChange}
          onBlur={handleInputBlur}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          min={min}
          max={max}
          step={step}
          className="flex-1 text-center text-lg font-semibold px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
        />

        {/* Increment Button */}
        <button
          type="button"
          onClick={handleIncrement}
          disabled={disabled || (max !== null && value >= max)}
          className="w-10 h-10 flex items-center justify-center bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:bg-gray-100 disabled:cursor-not-allowed transition-colors"
          aria-label="Increase servings"
        >
          <svg
            className="w-5 h-5 text-gray-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 4v16m8-8H4"
            />
          </svg>
        </button>
      </div>

      <div className="mt-2 space-y-1">
        <p className="text-sm text-gray-500">
          How many servings did you eat?{" "}
          {max !== null ? `(Range: ${min} - ${max})` : `(Minimum: ${min})`}
        </p>
        {predictedServings !== null && !isUsingPrediction && (
          <p className="text-sm text-gray-600">
            AI estimated:{" "}
            <span className="font-medium">{predictedServings}</span> servings
          </p>
        )}
      </div>
    </div>
  );
};

export default ServingsCountInput;
