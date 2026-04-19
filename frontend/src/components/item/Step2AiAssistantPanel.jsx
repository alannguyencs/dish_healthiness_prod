import React from "react";

/**
 * Step2AiAssistantPanel
 *
 * Stage 10 — inline textarea + Submit/Cancel panel that expands below
 * the Step 2 card's button row when the user clicks "AI Assistant Edit".
 *
 * Parent (Step2Results) owns the open/closed state and the hint value
 * so the textarea persists across re-renders while the revise call is
 * in flight. `assisting` disables Submit and the textarea while the
 * backend Gemini call is running.
 */
const Step2AiAssistantPanel = ({
  value,
  onChange,
  onSubmit,
  onCancel,
  assisting,
}) => {
  const trimmed = (value || "").trim();
  const canSubmit = trimmed.length > 0 && !assisting;

  return (
    <div
      className="bg-violet-50 border border-violet-200 rounded-lg p-4 mt-3 space-y-3"
      data-testid="step2-ai-assistant-panel"
    >
      <label className="block text-sm font-semibold text-violet-900">
        AI Assistant — describe the context you want the AI to consider
      </label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={assisting}
        rows={3}
        placeholder="e.g. Portions are smaller than the AI estimated — about 200 kcal per serving."
        className="block w-full rounded border-violet-300 shadow-sm text-sm resize-y disabled:opacity-60"
        data-testid="step2-ai-assistant-textarea"
      />
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={assisting}
          className="px-3 py-2 bg-white hover:bg-gray-100 text-gray-800 rounded border border-gray-300 text-sm font-semibold disabled:opacity-60"
          data-testid="step2-ai-assistant-cancel"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={!canSubmit}
          className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded text-sm font-semibold disabled:opacity-50"
          data-testid="step2-ai-assistant-submit"
        >
          {assisting ? "Revising…" : "Submit"}
        </button>
      </div>
    </div>
  );
};

export default Step2AiAssistantPanel;
