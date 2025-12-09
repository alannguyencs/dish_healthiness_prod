import React, { useState, useEffect, useRef } from 'react';

/**
 * ServingSizeSelector Component
 *
 * Dropdown selector for dish-specific serving sizes with custom input capability.
 * Options dynamically update based on selected dish.
 */
const ServingSizeSelector = ({
  options = [],
  selectedOption,
  onSelect,
  disabled = false,
  dishName = 'this dish'
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [customInput, setCustomInput] = useState('');
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Auto-select first option when options change
  useEffect(() => {
    if (options.length > 0 && !selectedOption) {
      onSelect(options[0]);
    }
  }, [options, selectedOption, onSelect]);

  const handleOptionClick = (option) => {
    onSelect(option);
    setIsOpen(false);
  };

  const handleCustomSubmit = (e) => {
    e.preventDefault();
    if (customInput.trim()) {
      onSelect(customInput.trim());
      setCustomInput('');
      setIsOpen(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  const isCustom = selectedOption && !options.includes(selectedOption);

  // Handle no options available (e.g., after reanalysis)
  if (!options || options.length === 0) {
    return (
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Serving Size
        </label>
        <input
          type="text"
          value={selectedOption || ''}
          onChange={(e) => onSelect(e.target.value)}
          placeholder="Enter serving size (e.g., 1 piece (85g))"
          disabled={disabled}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
        />
        <p className="mt-1 text-sm text-gray-500">Enter a custom serving size</p>
      </div>
    );
  }

  return (
    <div className="mb-4" ref={dropdownRef}>
      <label className="block text-sm font-medium text-gray-700 mb-2">
        Portion Sizes for {dishName}
      </label>

      {/* Dropdown Trigger */}
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        onKeyDown={handleKeyDown}
        className="w-full bg-white border border-gray-300 rounded-lg px-4 py-3 text-left focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 hover:bg-gray-50 transition-colors"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
      >
        <div className="flex items-center justify-between">
          <span className="font-medium text-gray-900">
            {selectedOption || 'Select serving size'}
          </span>
          <div className="flex items-center gap-2">
            {isCustom && (
              <span className="px-2 py-1 bg-purple-100 text-purple-800 text-xs font-semibold rounded">
                Custom
              </span>
            )}
            <svg
              className={`w-5 h-5 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute z-10 mt-2 w-full bg-white border border-gray-300 rounded-lg shadow-lg max-h-80 overflow-y-auto">
          {/* Serving Size Options */}
          <div className="p-2">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide px-3 py-2">
              Available Serving Sizes
            </div>
            {options.map((option, index) => (
              <button
                key={index}
                type="button"
                onClick={() => handleOptionClick(option)}
                className="w-full text-left px-3 py-2 hover:bg-gray-50 rounded transition-colors flex items-center justify-between"
                role="option"
                aria-selected={selectedOption === option}
              >
                <span className="font-medium text-gray-900">{option}</span>
                {selectedOption === option && (
                  <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
            ))}
          </div>

          {/* Custom Input Section */}
          <div className="border-t border-gray-200 p-3 bg-gray-50">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Or Enter Custom Size
            </div>
            <form onSubmit={handleCustomSubmit} className="flex gap-2">
              <input
                type="text"
                value={customInput}
                onChange={(e) => setCustomInput(e.target.value)}
                placeholder="e.g., 1.5 cups (200g)"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <button
                type="submit"
                disabled={!customInput.trim()}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
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

export default ServingSizeSelector;
