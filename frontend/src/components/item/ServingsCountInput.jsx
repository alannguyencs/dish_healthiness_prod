import React, { useState, useEffect } from 'react';

/**
 * ServingsCountInput Component
 *
 * Number input with increment/decrement controls for specifying servings consumed.
 * Validates range (0.1 - 10.0) and rounds to 1 decimal place.
 */
const ServingsCountInput = ({
  value = 1.0,
  onChange,
  disabled = false,
  min = 0.1,
  max = 10.0,
  step = 0.5
}) => {
  const [inputValue, setInputValue] = useState(value.toString());

  // Sync with prop changes
  useEffect(() => {
    setInputValue(value.toString());
  }, [value]);

  const handleIncrement = () => {
    const newValue = Math.min(max, value + step);
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
    } else if (numValue > max) {
      setInputValue(max.toString());
      onChange(max);
    } else {
      const rounded = Math.round(numValue * 10) / 10;
      setInputValue(rounded.toString());
      onChange(rounded);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      handleIncrement();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      handleDecrement();
    } else if (e.key === 'Enter') {
      e.target.blur();
    }
  };

  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        Number of Servings
      </label>

      <div className="flex items-center gap-3">
        {/* Decrement Button */}
        <button
          type="button"
          onClick={handleDecrement}
          disabled={disabled || value <= min}
          className="w-10 h-10 flex items-center justify-center bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:bg-gray-100 disabled:cursor-not-allowed transition-colors"
          aria-label="Decrease servings"
        >
          <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
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
          disabled={disabled || value >= max}
          className="w-10 h-10 flex items-center justify-center bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:bg-gray-100 disabled:cursor-not-allowed transition-colors"
          aria-label="Increase servings"
        >
          <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>

      <p className="mt-2 text-sm text-gray-500">
        How many servings did you eat? (Range: {min} - {max})
      </p>
    </div>
  );
};

export default ServingsCountInput;
