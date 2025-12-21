import React, { useState } from "react";
import DishNameSelector from "./DishNameSelector";
import ComponentListItem from "./ComponentListItem";
import AddComponentForm from "./AddComponentForm";

const Step1ComponentEditor = ({ step1Data, onConfirm, isConfirming }) => {
  const { dish_predictions = [], components = [] } = step1Data || {};

  // State for dish name selection
  const [selectedDishName, setSelectedDishName] = useState(
    dish_predictions[0]?.name || "",
  );
  const [customDishName, setCustomDishName] = useState("");
  const [useCustomDish, setUseCustomDish] = useState(false);
  const [showAllDishPredictions, setShowAllDishPredictions] = useState(false);

  // State for AI-predicted component selections
  const [componentSelections, setComponentSelections] = useState(() => {
    const initial = {};
    components.forEach((comp) => {
      initial[comp.component_name] = {
        enabled: true,
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
      id: Date.now(),
      component_name: newComponentName.trim(),
      selected_serving_size: newComponentServingSize.trim(),
      number_of_servings: newComponentServings,
    };

    setManualComponents((prev) => [...prev, newComp]);

    // Reset form and hide
    setNewComponentName("");
    setNewComponentServingSize("");
    setNewComponentServings(1.0);
    setShowAddComponent(false);
  };

  // Update manual component serving size
  const handleManualServingSizeChange = (componentName, servingSize) => {
    setManualComponents((prev) =>
      prev.map((comp) =>
        comp.component_name === componentName
          ? { ...comp, selected_serving_size: servingSize }
          : comp,
      ),
    );
  };

  // Update manual component servings
  const handleManualServingsChange = (componentName, servings) => {
    setManualComponents((prev) =>
      prev.map((comp) =>
        comp.component_name === componentName
          ? { ...comp, number_of_servings: parseFloat(servings) || 0.1 }
          : comp,
      ),
    );
  };

  // Remove manual component
  const handleRemoveManualComponent = (componentName) => {
    setManualComponents((prev) =>
      prev.filter((comp) => comp.component_name !== componentName),
    );
  };

  // Handle confirm button
  const handleConfirm = () => {
    // Get final dish name
    const finalDishName = useCustomDish ? customDishName : selectedDishName;

    if (!finalDishName.trim()) {
      alert("Please select or enter a dish name");
      return;
    }

    // Collect enabled AI components
    const enabledComponents = Object.entries(componentSelections)
      .filter(([, data]) => data.enabled)
      .map(([name, data]) => ({
        component_name: name,
        selected_serving_size: data.selected_serving_size,
        number_of_servings: data.number_of_servings,
      }));

    // Combine with manual components
    const allComponents = [...enabledComponents, ...manualComponents];

    if (allComponents.length === 0) {
      alert("Please select at least one component");
      return;
    }

    const confirmationData = {
      selected_dish_name: finalDishName,
      components: allComponents,
    };

    onConfirm(confirmationData);

    // Auto-scroll to show Step 2 loading
    setTimeout(() => {
      window.scrollBy({ top: 400, behavior: "smooth" });
    }, 100);
  };

  return (
    <div className="space-y-6">
      {/* Dish Name Selection */}
      <DishNameSelector
        dishPredictions={dish_predictions}
        selectedDishName={selectedDishName}
        customDishName={customDishName}
        useCustomDish={useCustomDish}
        showAllPredictions={showAllDishPredictions}
        onSelectDish={setSelectedDishName}
        onCustomDishChange={setCustomDishName}
        onUseCustomToggle={setUseCustomDish}
        onToggleShowAll={() =>
          setShowAllDishPredictions(!showAllDishPredictions)
        }
      />

      {/* Individual Dishes (Components) */}
      <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">
          Individual Dishes
        </h3>

        <div className="space-y-3 mb-4">
          {/* AI-predicted components */}
          {components.map((comp) => {
            const selection = componentSelections[comp.component_name] || {};
            return (
              <ComponentListItem
                key={comp.component_name}
                componentName={comp.component_name}
                servingSize={selection.selected_serving_size}
                numberOfServings={selection.number_of_servings}
                servingSizeOptions={selection.serving_size_options}
                enabled={selection.enabled}
                isManual={false}
                onToggle={handleComponentToggle}
                onServingSizeChange={handleComponentServingSizeChange}
                onServingsChange={handleComponentServingsChange}
              />
            );
          })}

          {/* Manual components */}
          {manualComponents.map((comp) => (
            <ComponentListItem
              key={comp.id}
              componentName={comp.component_name}
              servingSize={comp.selected_serving_size}
              numberOfServings={comp.number_of_servings}
              servingSizeOptions={[]}
              enabled={true}
              isManual={true}
              onServingSizeChange={handleManualServingSizeChange}
              onServingsChange={handleManualServingsChange}
              onRemove={handleRemoveManualComponent}
            />
          ))}
        </div>

        {/* Add component button/form */}
        {!showAddComponent ? (
          <button
            type="button"
            onClick={() => setShowAddComponent(true)}
            className="text-blue-600 hover:text-blue-700 font-medium text-sm flex items-center gap-1"
          >
            <span>+</span>
            <span>Add Custom Component</span>
          </button>
        ) : (
          <AddComponentForm
            componentName={newComponentName}
            servingSize={newComponentServingSize}
            numberOfServings={newComponentServings}
            onComponentNameChange={setNewComponentName}
            onServingSizeChange={setNewComponentServingSize}
            onServingsChange={setNewComponentServings}
            onAdd={handleAddManualComponent}
            onCancel={() => setShowAddComponent(false)}
          />
        )}
      </div>

      {/* Confirm Button */}
      <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
        <button
          onClick={handleConfirm}
          disabled={isConfirming}
          className={`w-full px-6 py-3 rounded-lg font-semibold ${
            isConfirming
              ? "bg-gray-400 cursor-not-allowed"
              : "bg-green-600 hover:bg-green-700"
          } text-white`}
        >
          {isConfirming ? "Confirming..." : "Confirm and Analyze Nutrition"}
        </button>

        {/* Metadata display */}
        {(step1Data.model ||
          step1Data.price_usd ||
          step1Data.analysis_time) && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="flex items-center gap-6 text-sm text-gray-600">
              {step1Data.model && (
                <div className="flex items-center gap-1.5">
                  <span>🤖</span>
                  <span>Model:</span>
                  <span className="font-medium">{step1Data.model}</span>
                </div>
              )}
              {step1Data.price_usd !== undefined && (
                <div className="flex items-center gap-1.5">
                  <span>💰</span>
                  <span>Cost:</span>
                  <span className="font-medium">
                    ${step1Data.price_usd.toFixed(4)}
                  </span>
                </div>
              )}
              {step1Data.analysis_time !== undefined && (
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
