import React, { useState } from "react";
import { Link } from "react-router-dom";
import DishNameSelector from "./DishNameSelector";
import ComponentListItem from "./ComponentListItem";
import AddComponentForm from "./AddComponentForm";

const Step1ComponentEditor = ({
  step1Data,
  confirmedData,
  onConfirm,
  isConfirming,
}) => {
  const { dish_predictions = [], components = [] } = step1Data || {};

  const getConfirmedComponent = (name) =>
    confirmedData?.components?.find((c) => c.component_name === name);
  const initDishName = confirmedData?.selected_dish_name || "";
  const isPredictedDish = dish_predictions.some((p) => p.name === initDishName);

  const [selectedDishName, setSelectedDishName] = useState(
    isPredictedDish ? initDishName : dish_predictions[0]?.name || "",
  );
  const [customDishName, setCustomDishName] = useState(
    initDishName && !isPredictedDish ? initDishName : "",
  );
  const [useCustomDish, setUseCustomDish] = useState(
    initDishName && !isPredictedDish,
  );
  const [showAllDishPredictions, setShowAllDishPredictions] = useState(false);
  const [componentSelections, setComponentSelections] = useState(() => {
    const initial = {};
    components.forEach((comp) => {
      const confirmed = getConfirmedComponent(comp.component_name);
      initial[comp.component_name] = {
        enabled: confirmed ? true : !confirmedData,
        selected_serving_size:
          confirmed?.selected_serving_size || comp.serving_sizes[0] || "",
        number_of_servings:
          confirmed?.number_of_servings || comp.predicted_servings || 1.0,
        serving_size_options: comp.serving_sizes || [],
      };
    });
    return initial;
  });
  const [manualComponents, setManualComponents] = useState(() => {
    if (!confirmedData?.components) return [];
    const origNames = components.map((c) => c.component_name);
    return confirmedData.components
      .filter((c) => !origNames.includes(c.component_name))
      .map((c, i) => ({ ...c, id: Date.now() + i }));
  });
  const [showAddComponent, setShowAddComponent] = useState(false);
  const [newComponentName, setNewComponentName] = useState("");
  const [newComponentServingSize, setNewComponentServingSize] = useState("");
  const [newComponentServings, setNewComponentServings] = useState(1.0);
  const handleComponentToggle = (componentName) => {
    setComponentSelections((prev) => ({
      ...prev,
      [componentName]: {
        ...prev[componentName],
        enabled: !prev[componentName].enabled,
      },
    }));
  };
  const handleComponentServingSizeChange = (componentName, servingSize) => {
    setComponentSelections((prev) => ({
      ...prev,
      [componentName]: {
        ...prev[componentName],
        selected_serving_size: servingSize,
      },
    }));
  };
  const handleComponentServingsChange = (componentName, servings) => {
    setComponentSelections((prev) => ({
      ...prev,
      [componentName]: {
        ...prev[componentName],
        number_of_servings: parseFloat(servings) || 0.1,
      },
    }));
  };

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
    setNewComponentName("");
    setNewComponentServingSize("");
    setNewComponentServings(1.0);
    setShowAddComponent(false);
  };

  const handleManualServingSizeChange = (componentName, servingSize) => {
    setManualComponents((prev) =>
      prev.map((comp) =>
        comp.component_name === componentName
          ? { ...comp, selected_serving_size: servingSize }
          : comp,
      ),
    );
  };

  const handleManualServingsChange = (componentName, servings) => {
    setManualComponents((prev) =>
      prev.map((comp) =>
        comp.component_name === componentName
          ? { ...comp, number_of_servings: parseFloat(servings) || 0.1 }
          : comp,
      ),
    );
  };

  const handleRemoveManualComponent = (componentName) => {
    setManualComponents((prev) =>
      prev.filter((comp) => comp.component_name !== componentName),
    );
  };

  const handleConfirm = () => {
    const finalDishName = useCustomDish ? customDishName : selectedDishName;

    if (!finalDishName.trim()) {
      alert("Please select or enter a dish name");
      return;
    }

    const enabledComponents = Object.entries(componentSelections)
      .filter(([, data]) => data.enabled)
      .map(([name, data]) => ({
        component_name: name,
        selected_serving_size: data.selected_serving_size,
        number_of_servings: data.number_of_servings,
      }));
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
    setTimeout(() => {
      window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
    }, 100);
  };

  return (
    <div className="space-y-6">
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

      <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-800">
            Individual Dishes
          </h3>
          <Link
            to="/reference/serving-size"
            target="_blank"
            className="text-sm text-blue-600 hover:text-blue-700"
          >
            ⓘ Serving Size Guide
          </Link>
        </div>

        <div className="space-y-3 mb-4">
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
