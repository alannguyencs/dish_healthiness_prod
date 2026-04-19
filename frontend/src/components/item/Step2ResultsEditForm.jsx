import React, { useState } from "react";

/**
 * Step2ResultsEditForm
 *
 * Stage 8 edit-mode renderer for Step 2 results. Flips all editable
 * Step 2 fields into controlled inputs: healthiness score + rationale,
 * five macros, and a micronutrient chip list (add/remove).
 *
 * Parent (Step2Results) owns the view/edit state and the server
 * round-trip via `onSave(payload)` / `onCancel()`. `saving` disables
 * Save while the POST is in flight.
 */
const Step2ResultsEditForm = ({ initialValues, onSave, onCancel, saving }) => {
  const [healthinessScore, setHealthinessScore] = useState(
    initialValues.healthiness_score,
  );
  const [rationale, setRationale] = useState(
    initialValues.healthiness_score_rationale,
  );
  const [calories, setCalories] = useState(initialValues.calories_kcal);
  const [fiber, setFiber] = useState(initialValues.fiber_g);
  const [carbs, setCarbs] = useState(initialValues.carbs_g);
  const [protein, setProtein] = useState(initialValues.protein_g);
  const [fat, setFat] = useState(initialValues.fat_g);
  const [micros, setMicros] = useState(
    // Normalize micronutrients (which may be List[str] or List[Micronutrient])
    // down to plain strings for the edit form.
    (initialValues.micronutrients || [])
      .map((m) => (typeof m === "string" ? m : m?.name))
      .filter(Boolean),
  );
  const [newMicro, setNewMicro] = useState("");

  const handleAddMicro = () => {
    const v = newMicro.trim();
    if (v && !micros.includes(v)) {
      setMicros([...micros, v]);
    }
    setNewMicro("");
  };

  const handleRemoveMicro = (idx) => {
    setMicros(micros.filter((_, i) => i !== idx));
  };

  const handleSubmit = () => {
    onSave({
      healthiness_score: parseInt(healthinessScore, 10),
      healthiness_score_rationale: rationale,
      calories_kcal: parseFloat(calories),
      fiber_g: parseFloat(fiber),
      carbs_g: parseFloat(carbs),
      protein_g: parseFloat(protein),
      fat_g: parseFloat(fat),
      micronutrients: micros,
    });
  };

  return (
    <div
      className="bg-white rounded-lg shadow-md p-6 space-y-6"
      data-testid="step2-edit-form"
    >
      <div className="border-b pb-4 flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-800">
          Edit Nutritional Analysis
        </h2>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-800 rounded font-semibold"
            data-testid="step2-edit-cancel"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={saving}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-semibold disabled:opacity-50"
            data-testid="step2-edit-save"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      <div className="space-y-3">
        <label className="block text-sm font-semibold text-gray-700">
          Healthiness score (0-100)
          <input
            type="number"
            min="0"
            max="100"
            value={healthinessScore}
            onChange={(e) => setHealthinessScore(e.target.value)}
            className="mt-1 block w-full rounded border-gray-300 shadow-sm"
            data-testid="step2-healthiness-score-input"
          />
        </label>
        <label className="block text-sm font-semibold text-gray-700">
          Rationale
          <textarea
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
            rows={4}
            className="mt-1 block w-full rounded border-gray-300 shadow-sm"
            data-testid="step2-rationale-input"
          />
        </label>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {[
          ["Calories (kcal)", calories, setCalories, "calories"],
          ["Fiber (g)", fiber, setFiber, "fiber"],
          ["Carbs (g)", carbs, setCarbs, "carbs"],
          ["Protein (g)", protein, setProtein, "protein"],
          ["Fat (g)", fat, setFat, "fat"],
        ].map(([label, value, setter, key]) => (
          <label
            key={key}
            className="block text-sm font-semibold text-gray-700"
          >
            {label}
            <input
              type="number"
              min="0"
              step="0.1"
              value={value}
              onChange={(e) => setter(e.target.value)}
              className="mt-1 block w-full rounded border-gray-300 shadow-sm"
              data-testid={`step2-${key}-input`}
            />
          </label>
        ))}
      </div>

      <div className="space-y-2">
        <div className="text-sm font-semibold text-gray-700">
          Micronutrients
        </div>
        <div className="flex flex-wrap gap-2">
          {micros.map((name, idx) => (
            <span
              key={`${name}-${idx}`}
              className="px-2 py-1 bg-purple-50 border border-purple-200 text-purple-700 rounded text-xs font-medium flex items-center gap-1"
              data-testid={`step2-micro-chip-${name}`}
            >
              {name}
              <button
                type="button"
                onClick={() => handleRemoveMicro(idx)}
                className="text-purple-500 hover:text-purple-700"
                aria-label={`Remove ${name}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={newMicro}
            onChange={(e) => setNewMicro(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleAddMicro();
              }
            }}
            placeholder="Add a micronutrient"
            className="flex-1 rounded border-gray-300 shadow-sm text-sm"
            data-testid="step2-micro-input"
          />
          <button
            type="button"
            onClick={handleAddMicro}
            className="px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded text-sm font-medium"
            data-testid="step2-micro-add"
          >
            + Add
          </button>
        </div>
      </div>
    </div>
  );
};

export default Step2ResultsEditForm;
