import React from "react";

/**
 * Top5DbMatches
 *
 * Stage 8 chip row showing up to 5 nutrition-database matches with
 * confidence badges. Reads from `result_gemini.nutrition_db_matches.nutrition_matches`.
 *
 * Hidden when the list is empty or absent — "always-visible reasoning,
 * optionally-visible evidence" design rule.
 *
 * Color bands:
 *   >= 85   green (strong match)
 *   70..84  yellow (acceptable)
 *   < 70    gray (weak — shown only because it was the top of the batch)
 */
const confidenceClass = (score) => {
  if (score >= 85) return "bg-green-50 border-green-300 text-green-800";
  if (score >= 70) return "bg-yellow-50 border-yellow-300 text-yellow-800";
  return "bg-gray-50 border-gray-300 text-gray-700";
};

const Top5DbMatches = ({ matches }) => {
  if (!matches || matches.length === 0) return null;

  const top5 = matches.slice(0, 5);

  return (
    <div
      className="bg-white rounded-lg shadow-md p-4"
      data-testid="top5-db-matches"
    >
      <h3 className="text-base font-semibold text-gray-800 mb-3">
        Top database matches
      </h3>
      <div className="flex flex-wrap gap-2">
        {top5.map((m, idx) => (
          <span
            key={`${m.matched_food_name}-${idx}`}
            className={`inline-flex items-center gap-2 px-3 py-1 border rounded-full text-sm ${confidenceClass(
              m.confidence_score || 0,
            )}`}
            title={`${m.source || ""} — ${m.confidence_score}%`}
            data-testid={`db-match-chip-${idx}`}
          >
            <span className="font-medium">
              {m.matched_food_name || "Unknown"}
            </span>
            <span className="text-xs font-semibold">
              {Math.round(m.confidence_score || 0)}%
            </span>
          </span>
        ))}
      </div>
    </div>
  );
};

export default Top5DbMatches;
