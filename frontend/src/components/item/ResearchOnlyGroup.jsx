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
    className="w-4 h-4 text-gray-400"
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
    className="w-4 h-4 text-gray-400"
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
    <div data-testid="research-only-group">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-controls="research-only-body"
        data-testid="research-only-toggle"
        className="w-full flex items-center gap-3 py-2 text-left"
      >
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
          Research only
        </span>
        <div className="flex-1 border-t border-gray-200" />
        {expanded ? CHEVRON_UP : CHEVRON_DOWN}
      </button>
      {expanded && (
        <div
          id="research-only-body"
          data-testid="research-only-body"
          className="space-y-6 mt-2"
        >
          {children}
        </div>
      )}
    </div>
  );
};

export default ResearchOnlyGroup;
