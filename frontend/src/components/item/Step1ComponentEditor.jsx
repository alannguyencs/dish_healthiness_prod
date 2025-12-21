import React, { useState } from "react";

/**
 * Step1ComponentEditor Component
 *
 * Displays Step 1 results (dish predictions and component predictions)
 * and allows user to confirm/modify before triggering Step 2.
 *
 * Features:
 * - Components are independent of dish name predictions
 * - Users can select/deselect components with checkboxes
 * - Users can add custom components manually
 */
const Step1ComponentEditor = ({ step1Data, onConfirm, isConfirming }) => {
  const { dish_predictions = [], components = [] } = step1Data || {};

  // State for dish name selection
  const [selectedDishName, setSelectedDishName] = useState(
    dish_predictions[0]?.name || "",
  );
  const [customDishName, setCustomDishName] = useState("");
  const [useCustomDish, setUseCustomDish] = useState(false);

  // State for AI-predicted component selections (component_name -> { enabled, serving_size, servings })
  const [componentSelections, setComponentSelections] = useState(() => {
    const initial = {};
    components.forEach((comp) => {
      initial[comp.component_name] = {
        enabled: true, // All components enabled by default
        selected_serving_size: comp.serving_sizes[0] || "",
        number_of_servings: comp.predicted_servings || 1.0,
        serving_size_options: comp.serving_sizes || [],
      };
    });
    return initial;
  });

  // State for manual components
  const [manualComponents, setManualComponents] = useState([]);
  const [showAddComponent, setShowAddComponent] = useState(false);
  const [newComponentName, setNewComponentName] = useState("");
  const [newComponentServingSize, setNewComponentServingSize] = useState("");
  const [newComponentServings, setNewComponentServings] = useState(1.0);

  // State for meal name dropdown
  const [showAllDishPredictions, setShowAllDishPredictions] = useState(false);

  // Toggle component enabled/disabled
  const handleComponentToggle = (componentName) => {
    setComponentSelections((prev) => ({
      ...prev,
      [componentName]: {
        ...prev[componentName],
        enabled: !prev[componentName].enabled,
      },
    }));
  };

  // Update serving size for a component
  const handleComponentServingSizeChange = (componentName, servingSize) => {
    setComponentSelections((prev) => ({
      ...prev,
      [componentName]: {
        ...prev[componentName],
        selected_serving_size: servingSize,
      },
    }));
  };

  // Update number of servings for a component
  const handleComponentServingsChange = (componentName, servings) => {
    setComponentSelections((prev) => ({
      ...prev,
      [componentName]: {
        ...prev[componentName],
        number_of_servings: parseFloat(servings) || 0.1,
      },
    }));
  };

  // Add manual component
  const handleAddManualComponent = () => {
    if (!newComponentName.trim() || !newComponentServingSize.trim()) {
      alert("Please enter both component name and serving size");
      return;
    }

    const newComp = {
      id: Date.now(), // Unique ID for manual components
      component_name: newComponentName.trim(),
      selected_serving_size: newComponentServingSize.trim(),
      number_of_servings: newComponentServings,
    };

    setManualComponents((prev) => [...prev, newComp]);

    // Reset form
    setNewComponentName("");
    setNewComponentServingSize("");
    setNewComponentServings(1.0);
    setShowAddComponent(false);
  };

  // Remove manual component
  const handleRemoveManualComponent = (id) => {
    setManualComponents((prev) => prev.filter((c) => c.id !== id));
  };

  // Confirm and trigger Step 2
  const handleConfirm = () => {
    const finalDishName = useCustomDish ? customDishName : selectedDishName;

    if (!finalDishName.trim()) {
      alert("Please select or enter a dish name");
      return;
    }

    // Collect enabled AI components
    const enabledAIComponents = components
      .filter((comp) => componentSelections[comp.component_name]?.enabled)
      .map((comp) => ({
        component_name: comp.component_name,
        selected_serving_size:
          componentSelections[comp.component_name]?.selected_serving_size ||
          comp.serving_sizes[0],
        number_of_servings:
          componentSelections[comp.component_name]?.number_of_servings || 1.0,
      }));

    // Collect manual components
    const enabledManualComponents = manualComponents.map((comp) => ({
      component_name: comp.component_name,
      selected_serving_size: comp.selected_serving_size,
      number_of_servings: comp.number_of_servings,
    }));

    // Combine all components
    const allComponents = [...enabledAIComponents, ...enabledManualComponents];

    if (allComponents.length === 0) {
      alert("Please select at least one component or add a manual component");
      return;
    }

    // Build confirmation data
    const confirmationData = {
      selected_dish_name: finalDishName,
      components: allComponents,
    };

    onConfirm(confirmationData);

    // Scroll down to show the loading indicator
    setTimeout(() => {
      window.scrollBy({
        top: 400,
        behavior: "smooth",
      });
    }, 100);
  };

  if (!step1Data || !components.length) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <p className="text-yellow-800">No Step 1 data available.</p>
      </div>
    );
  }

  const enabledCount =
    Object.values(componentSelections).filter((c) => c.enabled).length +
    manualComponents.length;

  return (
    <div className="bg-white rounded-lg shadow-md p-6 space-y-6">
      <div className="border-b pb-4">
        <h2 className="text-2xl font-bold text-gray-800">
          Step 1: Confirm Meal & Individual Dishes
        </h2>
        <p className="text-gray-600 mt-1">
          Select individual dishes, adjust serving sizes, and add custom dishes
          as needed.
        </p>
      </div>

      {/* Meal Name Selection */}
      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-gray-800">
          Overall Meal Name
        </h3>
        <div className="space-y-2">
          {/* Top prediction with dropdown button */}
          {dish_predictions.slice(0, 1).map((pred, idx) => (
            <div key={idx}>
              <label className="flex items-center space-x-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer">
                <input
                  type="radio"
                  name="dishName"
                  value={pred.name}
                  checked={!useCustomDish && selectedDishName === pred.name}
                  onChange={(e) => {
                    setSelectedDishName(e.target.value);
                    setUseCustomDish(false);
                  }}
                  className="form-radio h-4 w-4 text-blue-600"
                />
                <div className="flex-1 flex items-center justify-between">
                  <div>
                    <span className="font-medium text-gray-800">
                      {pred.name}
                    </span>
                    <span className="ml-2 text-sm text-gray-500">
                      ({(pred.confidence * 100).toFixed(0)}% confidence)
                    </span>
                  </div>
                  {(dish_predictions.length > 1 || true) && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        setShowAllDishPredictions(!showAllDishPredictions);
                      }}
                      className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1 ml-4"
                    >
                      {showAllDishPredictions ? (
                        <>
                          <svg
                            className="w-4 h-4"
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
                          Hide
                        </>
                      ) : (
                        <>
                          <svg
                            className="w-4 h-4"
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
                          {dish_predictions.length > 1
                            ? `${dish_predictions.length} more`
                            : "More"}
                        </>
                      )}
                    </button>
                  )}
                </div>
              </label>
            </div>
          ))}

          {/* Remaining predictions - collapsible */}
          {showAllDishPredictions && (
            <>
              {dish_predictions.slice(1).map((pred, idx) => (
                <label
                  key={idx + 1}
                  className="flex items-center space-x-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer"
                >
                  <input
                    type="radio"
                    name="dishName"
                    value={pred.name}
                    checked={!useCustomDish && selectedDishName === pred.name}
                    onChange={(e) => {
                      setSelectedDishName(e.target.value);
                      setUseCustomDish(false);
                    }}
                    className="form-radio h-4 w-4 text-blue-600"
                  />
                  <div className="flex-1">
                    <span className="font-medium text-gray-800">
                      {pred.name}
                    </span>
                    <span className="ml-2 text-sm text-gray-500">
                      ({(pred.confidence * 100).toFixed(0)}% confidence)
                    </span>
                  </div>
                </label>
              ))}

              {/* Custom dish name option - in dropdown */}
              <label className="flex items-start space-x-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer">
                <input
                  type="radio"
                  name="dishName"
                  checked={useCustomDish}
                  onChange={() => setUseCustomDish(true)}
                  className="form-radio h-4 w-4 text-blue-600 mt-1"
                />
                <div className="flex-1">
                  <span className="font-medium text-gray-800">
                    Custom dish name
                  </span>
                  {useCustomDish && (
                    <input
                      type="text"
                      value={customDishName}
                      onChange={(e) => setCustomDishName(e.target.value)}
                      placeholder="Enter custom dish name..."
                      className="mt-2 w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      autoFocus
                    />
                  )}
                </div>
              </label>
            </>
          )}
        </div>
      </div>

      {/* AI-Predicted Individual Dishes Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-800">
            Individual Dishes
          </h3>
          <span className="text-sm text-gray-600">
            {enabledCount} dish{enabledCount !== 1 ? "es" : ""} selected
          </span>
        </div>

        <div className="space-y-3">
          {components.map((comp, idx) => {
            const selection = componentSelections[comp.component_name];
            const isEnabled = selection?.enabled;

            return (
              <div
                key={idx}
                className={`border rounded-lg p-4 transition-all ${
                  isEnabled
                    ? "bg-gray-50 border-gray-300"
                    : "bg-gray-100 border-gray-200 opacity-60"
                }`}
              >
                {/* Component header with checkbox */}
                <div className="flex items-start space-x-3 mb-3">
                  <input
                    type="checkbox"
                    checked={isEnabled}
                    onChange={() => handleComponentToggle(comp.component_name)}
                    className="h-5 w-5 text-blue-600 rounded mt-0.5"
                  />
                  <div className="flex-1">
                    <h4 className="font-semibold text-gray-800 capitalize">
                      {comp.component_name}
                    </h4>
                  </div>
                </div>

                {/* Serving details (only shown when enabled) */}
                {isEnabled && (
                  <div className="ml-8">
                    <div className="grid grid-cols-[110px_minmax(200px,1fr)_160px_80px] gap-3 items-center text-sm">
                      <span className="text-gray-700 font-medium">
                        Serving Size:
                      </span>
                      <select
                        value={selection.selected_serving_size}
                        onChange={(e) =>
                          handleComponentServingSizeChange(
                            comp.component_name,
                            e.target.value,
                          )
                        }
                        className="px-2 py-1 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                      >
                        {comp.serving_sizes.map((size, sIdx) => (
                          <option key={sIdx} value={size}>
                            {size}
                          </option>
                        ))}
                      </select>
                      <span className="text-gray-700 font-medium">
                        Number of Servings:
                      </span>
                      <input
                        type="number"
                        min="0.1"
                        max="10"
                        step="0.1"
                        value={selection.number_of_servings}
                        onChange={(e) =>
                          handleComponentServingsChange(
                            comp.component_name,
                            e.target.value,
                          )
                        }
                        className="px-2 py-1 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                      />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Manual Dishes Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-800">
            Add Custom Dishes
          </h3>
          <button
            onClick={() => setShowAddComponent(!showAddComponent)}
            className="text-blue-600 hover:text-blue-700 font-medium text-sm"
          >
            {showAddComponent ? "− Cancel" : "+ Add Dish"}
          </button>
        </div>

        {/* Add Dish Form */}
        {showAddComponent && (
          <div className="border border-blue-200 rounded-lg p-4 bg-blue-50 space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Dish Name
              </label>
              <input
                type="text"
                value={newComponentName}
                onChange={(e) => setNewComponentName(e.target.value)}
                placeholder="e.g., Side Salad, Garlic Bread, Soup"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Serving Size
              </label>
              <input
                type="text"
                value={newComponentServingSize}
                onChange={(e) => setNewComponentServingSize(e.target.value)}
                placeholder="e.g., 2 tbsp, 1 cup, 50g"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Number of Servings
              </label>
              <input
                type="number"
                min="0.1"
                max="10"
                step="0.1"
                value={newComponentServings}
                onChange={(e) =>
                  setNewComponentServings(parseFloat(e.target.value) || 0.1)
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <button
              onClick={handleAddManualComponent}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded-lg"
            >
              Add Dish
            </button>
          </div>
        )}

        {/* Manual Components List */}
        {manualComponents.length > 0 && (
          <div className="space-y-3">
            {manualComponents.map((comp) => (
              <div
                key={comp.id}
                className="border border-green-300 rounded-lg p-4 bg-green-50"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h4 className="font-semibold text-gray-800 capitalize">
                      {comp.component_name}
                      <span className="ml-2 text-xs text-green-600 font-normal">
                        (Manual)
                      </span>
                    </h4>
                    <p className="text-sm text-gray-600 mt-1">
                      {comp.selected_serving_size} × {comp.number_of_servings}
                    </p>
                  </div>
                  <button
                    onClick={() => handleRemoveManualComponent(comp.id)}
                    className="text-red-600 hover:text-red-700 text-sm font-medium"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Confirm Button */}
      <div className="pt-4 border-t space-y-3">
        <button
          onClick={handleConfirm}
          disabled={isConfirming || enabledCount === 0}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
        >
          {isConfirming
            ? "Confirming & Running Analysis..."
            : `Confirm & Calculate Nutrition (${enabledCount} dish${enabledCount !== 1 ? "es" : ""})`}
        </button>
        {enabledCount === 0 && (
          <p className="text-sm text-red-600 text-center mt-2">
            Please select at least one dish
          </p>
        )}

        {/* Model/Cost/Time Info */}
        {(step1Data.model ||
          step1Data.price_usd ||
          step1Data.analysis_time) && (
          <div className="pt-3 border-t text-sm text-gray-500">
            <div className="flex items-center gap-6">
              {step1Data.model && (
                <div className="flex items-center gap-1.5">
                  <span>🤖</span>
                  <span>Model:</span>
                  <span className="font-medium">{step1Data.model}</span>
                </div>
              )}
              {step1Data.price_usd && (
                <div className="flex items-center gap-1.5">
                  <span>💰</span>
                  <span>Cost:</span>
                  <span className="font-medium">
                    ${step1Data.price_usd.toFixed(4)}
                  </span>
                </div>
              )}
              {step1Data.analysis_time && (
                <div className="flex items-center gap-1.5">
                  <span>⏱️</span>
                  <span>Time:</span>
                  <span className="font-medium">
                    {step1Data.analysis_time}s
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Step1ComponentEditor;
