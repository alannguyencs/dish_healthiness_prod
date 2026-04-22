import React from "react";

/**
 * ReasoningPanel
 *
 * Stage 8 panel that renders the seven `reasoning_*` strings from
 * `nutrition_data` (the AI's original rationale — even when the user
 * has overridden the numbers, the AI's reasoning stays visible as
 * audit).
 *
 * The panel's own collapse toggle was removed: the outer
 * <ResearchOnlyGroup> chevron is the single source of open/closed for
 * all research panels. Rendering here is non-conditional — if
 * nutritionData is present, the body shows.
 *
 * Empty-string reasoning_* fields render as a muted placeholder so the
 * user can see every metric has been accounted for.
 */
const FIELDS = [
  ["reasoning_sources", "Sources"],
  ["reasoning_calories", "Calories"],
  ["reasoning_fiber", "Fiber"],
  ["reasoning_carbs", "Carbs"],
  ["reasoning_protein", "Protein"],
  ["reasoning_fat", "Fat"],
  ["reasoning_micronutrients", "Micronutrients"],
];

const ReasoningPanel = ({ nutritionData }) => {
  if (!nutritionData) return null;

  return (
    <div
      className="bg-white rounded-lg shadow-md p-4"
      data-testid="reasoning-panel"
    >
      <h3 className="text-base font-semibold text-gray-800">
        Why these numbers?
      </h3>
      <div className="mt-3 space-y-2" data-testid="reasoning-panel-body">
        {FIELDS.map(([key, label]) => {
          const text = nutritionData[key];
          const body = text && text.trim() ? text : "No rationale provided.";
          return (
            <div
              key={key}
              className="border-t border-gray-100 pt-2 first:border-t-0 first:pt-0"
              data-testid={`reasoning-${key}`}
            >
              <div className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                {label}
              </div>
              <div
                className={`text-sm ${
                  text && text.trim() ? "text-gray-700" : "text-gray-400 italic"
                }`}
              >
                {body}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ReasoningPanel;
