import React from "react";

const SOFT_RETRY_CAP = 5;

/**
 * PhaseErrorCard
 *
 * Renders the surfaced error state for a failed Phase 1 (component
 * identification) or Phase 2 (nutritional analysis) call. Caller passes the
 * `headline` so this component is phase-agnostic. Hides the retry button for
 * `error_type === "config_error"` and swaps to a "Try Anyway" warning once the
 * user has retried at least SOFT_RETRY_CAP times.
 */
const PhaseErrorCard = ({ headline, error, onRetry, isRetrying }) => {
  if (!error) return null;

  const { error_type, message, retry_count = 0 } = error;
  const canRetry = error_type !== "config_error";
  const exceededSoftCap = retry_count >= SOFT_RETRY_CAP;

  const buttonLabel = isRetrying
    ? "Retrying..."
    : exceededSoftCap
      ? "Try Anyway"
      : "Try Again";

  return (
    <div className="mt-8 p-6 bg-red-50 rounded-lg border border-red-200">
      <div className="flex items-start gap-3">
        <svg
          className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01M5.07 19h13.86c1.54 0 2.5-1.67 1.73-3L13.73
               4a2 2 0 00-3.46 0L3.34 16c-.77 1.33.19 3 1.73 3z"
          />
        </svg>
        <div className="flex-1">
          <h3 className="text-base font-semibold text-red-800">{headline}</h3>
          <p className="mt-1 text-sm text-red-700">{message}</p>

          {exceededSoftCap && canRetry && (
            <p className="mt-2 text-sm text-red-700 font-medium">
              We&rsquo;ve tried {retry_count} times. This is unlikely to succeed
              without a fix on our side.
            </p>
          )}

          <div className="mt-4 flex items-center gap-3">
            {canRetry && (
              <button
                type="button"
                onClick={onRetry}
                disabled={isRetrying}
                className="bg-red-600 hover:bg-red-700 disabled:opacity-60
                           disabled:cursor-not-allowed text-white text-sm
                           font-semibold py-2 px-4 rounded-lg"
              >
                {buttonLabel}
              </button>
            )}
            {retry_count > 0 && (
              <span className="text-xs text-red-600">
                Previous attempts: {retry_count}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PhaseErrorCard;
