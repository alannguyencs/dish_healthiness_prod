import React, { useState } from "react";

import Step2AiAssistantPanel from "./Step2AiAssistantPanel";
import Step2ResultsEditForm from "./Step2ResultsEditForm";
import { resolveHealthinessTier } from "../../utils/healthiness";

/**
 * Step2Results Component
 *
 * Displays Step 2 nutritional analysis results after user confirmation.
 * Stage 8: Manual Edit toggle flips the card into an edit form. Stage 10
 * adds a parallel "AI Assistant Edit" button that expands an inline
 * textarea; Submit POSTs the hint to the backend which revises the
 * payload via Gemini 2.5 Pro and commits directly (no preview step).
 */
const Step2Results = ({
  step2Data,
  step2Corrected,
  onEditSave,
  saving,
  onAiAssistSubmit,
  aiAssisting,
}) => {
  const [editing, setEditing] = useState(false);
  const [aiHintOpen, setAiHintOpen] = useState(false);
  const [aiHint, setAiHint] = useState("");

  if (!step2Data) {
    return (
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-blue-800">Step 2 analysis in progress...</p>
      </div>
    );
  }

  const activeData = step2Corrected || step2Data;
  const isCorrected = !!step2Corrected;

  if (editing) {
    return (
      <Step2ResultsEditForm
        initialValues={{
          healthiness_score: activeData.healthiness_score,
          healthiness_score_rationale: activeData.healthiness_score_rationale,
          calories_kcal: activeData.calories_kcal,
          fiber_g: activeData.fiber_g,
          carbs_g: activeData.carbs_g,
          protein_g: activeData.protein_g,
          fat_g: activeData.fat_g,
          micronutrients: activeData.micronutrients || [],
        }}
        saving={saving}
        onCancel={() => setEditing(false)}
        onSave={async (payload) => {
          await onEditSave(payload);
          setEditing(false);
        }}
      />
    );
  }

  const {
    dish_name,
    healthiness_score,
    healthiness_score_rationale,
    calories_kcal,
    fiber_g,
    carbs_g,
    protein_g,
    fat_g,
    micronutrients = [],
  } = activeData;

  const tier = resolveHealthinessTier(healthiness_score);

  return (
    <div className="bg-white rounded-lg shadow-md p-6 space-y-6">
      <div className="border-b pb-4 flex items-center justify-between">
        <div>
          <p className="text-2xl font-bold text-blue-600">
            {dish_name || step2Data.dish_name}
          </p>
          {isCorrected && (
            <span
              className="mt-1 inline-block px-2 py-0.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded text-xs font-semibold"
              data-testid="step2-corrected-badge"
            >
              Corrected by you
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {onEditSave && (
            <button
              type="button"
              onClick={() => setEditing(true)}
              disabled={aiAssisting}
              className="px-3 py-1 bg-gray-100 hover:bg-gray-200 text-gray-800 rounded text-sm font-semibold disabled:opacity-50 inline-flex items-center gap-1.5"
              data-testid="step2-edit-toggle"
            >
              <span aria-hidden="true">✏️</span>
              <span>Manual Edit</span>
            </button>
          )}
          {onAiAssistSubmit && (
            <button
              type="button"
              onClick={() => setAiHintOpen((v) => !v)}
              disabled={aiAssisting}
              className="px-3 py-1 bg-violet-100 hover:bg-violet-200 text-violet-900 rounded text-sm font-semibold disabled:opacity-50 inline-flex items-center gap-1.5"
              data-testid="step2-ai-assistant-toggle"
            >
              <span aria-hidden="true">{aiAssisting ? "⏳" : "✨"}</span>
              <span>{aiAssisting ? "Revising…" : "AI Assistant Edit"}</span>
            </button>
          )}
        </div>
      </div>

      {aiHintOpen && onAiAssistSubmit && (
        <Step2AiAssistantPanel
          value={aiHint}
          onChange={setAiHint}
          assisting={!!aiAssisting}
          onCancel={() => {
            setAiHint("");
            setAiHintOpen(false);
          }}
          onSubmit={async () => {
            const trimmed = aiHint.trim();
            if (!trimmed) return;
            await onAiAssistSubmit(trimmed);
            setAiHint("");
            setAiHintOpen(false);
          }}
        />
      )}

      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold text-gray-800">Healthiness</h3>
          <div
            className={`px-3 py-1.5 rounded-lg text-base font-semibold ${tier.color}`}
          >
            {tier.label}
          </div>
        </div>
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <p className="text-gray-700 leading-relaxed">
            {healthiness_score_rationale}
          </p>
        </div>
      </div>

      <div className="space-y-2">
        <h3 className="text-lg font-semibold text-gray-800 mb-3">
          Nutritional Information
        </h3>

        <div className="space-y-1">
          <div className="flex items-center justify-between py-2 border-b border-gray-200">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <span className="text-lg">🔥</span>
                <span className="text-gray-700">Calories (kcal)</span>
                <span className="font-semibold text-gray-800">
                  {calories_kcal}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-lg">🌾</span>
                <span className="text-gray-700">Fiber (g)</span>
                <span className="font-semibold text-gray-800">{fiber_g}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between py-2 border-b border-gray-200">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <span className="text-lg">🍞</span>
                <span className="text-gray-700">Carbs (g)</span>
                <span className="font-semibold text-gray-800">{carbs_g}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-lg">🍖</span>
                <span className="text-gray-700">Protein (g)</span>
                <span className="font-semibold text-gray-800">{protein_g}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-lg">🧈</span>
                <span className="text-gray-700">Fat (g)</span>
                <span className="font-semibold text-gray-800">{fat_g}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {micronutrients.length > 0 && (
        <div className="py-2 border-b border-gray-200">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="text-lg">🍊</span>
              <span className="text-gray-700">Micronutrients</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {micronutrients.map((nutrient, idx) => {
                const name =
                  typeof nutrient === "string" ? nutrient : nutrient?.name;
                const amount_mg =
                  typeof nutrient === "string" ? null : nutrient?.amount_mg;
                if (!name) return null;
                return (
                  <span
                    key={idx}
                    className="px-2 py-1 bg-purple-50 border border-purple-200 text-purple-700 rounded text-xs font-medium"
                  >
                    {amount_mg != null ? `${name} (${amount_mg}mg)` : name}
                  </span>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {(step2Data.model || step2Data.price_usd || step2Data.analysis_time) && (
        <div className="pt-4 border-t text-sm text-gray-500">
          <div className="flex items-center gap-6">
            {step2Data.model && (
              <div className="flex items-center gap-1.5">
                <span>🤖</span>
                <span>Model:</span>
                <span className="font-medium">{step2Data.model}</span>
              </div>
            )}
            {step2Data.price_usd && (
              <div className="flex items-center gap-1.5">
                <span>💰</span>
                <span>Cost:</span>
                <span className="font-medium">
                  ${step2Data.price_usd.toFixed(4)}
                </span>
              </div>
            )}
            {step2Data.analysis_time && (
              <div className="flex items-center gap-1.5">
                <span>⏱️</span>
                <span>Time:</span>
                <span className="font-medium">{step2Data.analysis_time}s</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Step2Results;
