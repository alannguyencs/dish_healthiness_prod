import React, { useState } from "react";
import { Link } from "react-router-dom";

/**
 * PersonalizedDataCard — research-only surface on the Step 1 view.
 *
 * Exposes the Phase 1.1.1(a) flash caption and the Phase 1.1.1(b) top-1
 * retrieval hit. Collapsed by default; the chevron toggle reveals the
 * body. Rendered only when the Step 1 editor is rendered (see ItemV2).
 *
 * Props:
 *   flashCaption (string | null | undefined) — verbatim Gemini Flash caption
 *     for the current upload. Falls back to an explanatory message when
 *     null (Flash failure or legacy row without the field).
 *   referenceImage (object | null | undefined) — the Phase 1.1.1(b) hit:
 *     { query_id, image_url, description, similarity_score, prior_step1_data }
 *     or null on cold start / below-threshold.
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

const PersonalizedDataCard = ({ flashCaption, referenceImage }) => {
  const [expanded, setExpanded] = useState(false);
  const hasCaption =
    typeof flashCaption === "string" && flashCaption.length > 0;
  const hasReference = Boolean(referenceImage);

  return (
    <div
      className="bg-white rounded-lg shadow-md p-4"
      data-testid="personalized-data-card"
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-controls="personalized-data-body"
        data-testid="personalized-data-toggle"
        className="w-full flex items-center justify-between text-left"
      >
        <span className="text-sm font-semibold text-gray-500">
          Personalized Data (Research only)
        </span>
        {expanded ? CHEVRON_UP : CHEVRON_DOWN}
      </button>

      {expanded && (
        <div id="personalized-data-body" className="mt-4 space-y-4">
          <section data-testid="personalized-data-flash-caption">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
              Flash Caption (Phase 1.1.1(a))
            </h3>
            {hasCaption ? (
              <p className="text-sm text-gray-800 italic">{flashCaption}</p>
            ) : (
              <p className="text-sm text-gray-400 italic">
                No caption generated (Flash call unavailable).
              </p>
            )}
          </section>

          <section data-testid="personalized-data-reference">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
              Most Relevant Prior Item (Phase 1.1.1(b))
            </h3>
            {hasReference ? (
              <Link
                to={`/item/${referenceImage.query_id}`}
                className="block border border-gray-200 rounded-md p-2 flex gap-3 hover:bg-gray-50 transition"
              >
                {referenceImage.image_url && (
                  <img
                    src={referenceImage.image_url}
                    alt=""
                    loading="lazy"
                    className="w-16 h-16 object-cover rounded flex-shrink-0"
                  />
                )}
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs text-gray-500 truncate">
                      Query #{referenceImage.query_id}
                    </span>
                    <span className="px-2 py-0.5 bg-blue-50 border border-blue-200 text-blue-800 rounded text-xs font-semibold">
                      {Number(referenceImage.similarity_score ?? 0).toFixed(2)}{" "}
                      sim
                    </span>
                  </div>
                  <p className="text-sm text-gray-700 line-clamp-2">
                    {referenceImage.description || "(no caption)"}
                  </p>
                </div>
              </Link>
            ) : (
              <p className="text-sm text-gray-400 italic">
                No prior match — cold-start upload or below 0.25 threshold.
              </p>
            )}
          </section>
        </div>
      )}
    </div>
  );
};

export default PersonalizedDataCard;
