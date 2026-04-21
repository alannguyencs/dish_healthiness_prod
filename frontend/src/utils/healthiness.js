// Single source of truth for healthiness-score → label/color buckets.
// Tiers must be in DESCENDING order; resolveHealthinessTier picks the first
// whose `min` is satisfied, with the trailing `min: 0` tier as the fallback.
export const HEALTHINESS_TIERS = [
  { min: 81, label: "Very Healthy", color: "text-green-600 bg-green-100" },
  { min: 61, label: "Healthy", color: "text-green-500 bg-green-50" },
  { min: 41, label: "Moderate", color: "text-yellow-600 bg-yellow-100" },
  { min: 21, label: "Unhealthy", color: "text-orange-600 bg-orange-100" },
  { min: 0, label: "Very Unhealthy", color: "text-red-600 bg-red-100" },
];

export const resolveHealthinessTier = (score) =>
  HEALTHINESS_TIERS.find((tier) => score >= tier.min) ??
  HEALTHINESS_TIERS[HEALTHINESS_TIERS.length - 1];
