import React from "react";

/**
 * PersonalizationMatches
 *
 * Stage 8 card list showing up to K historical matches from the user's
 * own upload corpus (Stage 6's `result_gemini.personalized_matches`).
 *
 * Each card shows thumbnail + description + similarity badge + macros.
 * When the match carries `corrected_step2_data` (Stage 8 write from a
 * prior correction the user made on this dish), the card prefers those
 * nutrients over `prior_step2_data` and shows a "User-verified" badge.
 *
 * Hidden when the list is empty or absent.
 */
const MACRO_ROWS = [
  ["calories_kcal", "Calories (kcal)"],
  ["fiber_g", "Fiber (g)"],
  ["carbs_g", "Carbs (g)"],
  ["protein_g", "Protein (g)"],
  ["fat_g", "Fat (g)"],
];

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:2612";

const resolveImageUrl = (url) => {
  if (!url) return null;
  if (/^https?:\/\//i.test(url)) return url;
  return `${API_BASE}${url}`;
};

const PersonalizationMatches = ({ matches }) => {
  if (!matches || matches.length === 0) return null;

  return (
    <div
      className="bg-white rounded-lg shadow-md p-4 space-y-3"
      data-testid="personalization-matches"
    >
      <h3 className="text-base font-semibold text-gray-800">
        Your prior similar dishes
      </h3>
      <div className="space-y-3">
        {matches.map((m, idx) => {
          const activeNutrients =
            m.corrected_step2_data || m.prior_step2_data || {};
          const userVerified = !!m.corrected_step2_data;
          const similarityPct = Math.round((m.similarity_score || 0) * 100);
          return (
            <div
              key={`${m.query_id}-${idx}`}
              className="border border-gray-200 rounded-md p-3 flex gap-3"
              data-testid={`persona-card-${m.query_id}`}
            >
              {m.image_url && (
                <img
                  src={resolveImageUrl(m.image_url)}
                  alt={m.description || "Prior upload"}
                  loading="lazy"
                  className="w-16 h-16 object-cover rounded flex-shrink-0"
                />
              )}
              <div className="flex-1 min-w-0 space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm text-gray-700 truncate">
                    {m.description || "Prior upload"}
                  </span>
                  <span className="px-2 py-0.5 bg-blue-50 border border-blue-200 text-blue-800 rounded text-xs font-semibold">
                    {similarityPct}% similar
                  </span>
                  {userVerified && (
                    <span
                      className="px-2 py-0.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded text-xs font-semibold"
                      data-testid={`persona-user-verified-${m.query_id}`}
                    >
                      User-verified
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-x-3 gap-y-1 text-xs text-gray-600">
                  {MACRO_ROWS.map(([key, label]) => {
                    const value = activeNutrients[key];
                    if (value == null) return null;
                    return (
                      <div key={key}>
                        <span className="text-gray-500">{label}: </span>
                        <span className="font-medium text-gray-800">
                          {value}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default PersonalizationMatches;
