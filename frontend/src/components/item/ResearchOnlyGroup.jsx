import React, { useState } from "react";

/**
 * ResearchOnlyGroup — collapsible wrapper for Step 2's debug/research panels.
 *
 * Hides ReasoningPanel, Top5DbMatches, and PersonalizationMatches behind a
 * single chevron toggle. Collapsed by default so the primary Step 2 card
 * stays the visual focus; reviewers / PMs click the chevron to reveal the
 * debug surface. Mirrors the PersonalizedDataCard pattern used on Step 1.
 */
const CHEVRON_DOWN = (
  <svg
    className="w-5 h-5 text-gray-500"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    aria-hidden="true"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M19 9l-7 7-7-7"
    />
  </svg>
);

const CHEVRON_UP = (
  <svg
    className="w-5 h-5 text-gray-500"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    aria-hidden="true"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M5 15l7-7 7 7"
    />
  </svg>
);

const ResearchOnlyGroup = ({ children }) => {
  const [expanded, setExpanded] = useState(false);
  return (
    <div data-testid="research-only-group" className="space-y-6">
      <div className="bg-white rounded-lg shadow-md p-4">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          aria-controls="research-only-body"
          data-testid="research-only-toggle"
          className="w-full flex items-center justify-between text-left"
        >
          <span className="text-sm font-semibold text-gray-500">
            Research only
          </span>
          {expanded ? CHEVRON_UP : CHEVRON_DOWN}
        </button>
      </div>
      {expanded && (
        <div
          id="research-only-body"
          data-testid="research-only-body"
          className="space-y-6"
        >
          {children}
        </div>
      )}
    </div>
  );
};

export default ResearchOnlyGroup;
