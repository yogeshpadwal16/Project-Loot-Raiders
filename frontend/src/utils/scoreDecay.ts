import { DealItem } from "../types/api";

/**
 * Calculates temporal decay multiplier based on deal age.
 * Age schedule:
 * - 0–6 hours:   1.00 (100% raw score)
 * - 6–24 hours:  0.95 (95% raw score)
 * - 1–3 days:    0.85 (85% raw score)
 * - 3–7 days:    0.70 (70% raw score)
 * - >7 days:     0.60 (60% raw score)
 * 
 * Historical-low protection:
 * Verified all-time lows receive a +0.08 score retention resilience boost.
 */
export function getEffectiveDealScore(deal: DealItem, nowEpochSeconds: number = Date.now() / 1000): number {
  const rawScore = Number(deal.deal_score) || 0;
  if (rawScore <= 0) return 0;

  const dealTimestamp = Number(deal.timestamp) || 0;
  if (!dealTimestamp || dealTimestamp <= 0) return rawScore;

  const ageHours = Math.max(0, (nowEpochSeconds - dealTimestamp) / 3600);

  let baseMultiplier = 1.0;
  if (ageHours <= 6) {
    baseMultiplier = 1.0;
  } else if (ageHours <= 24) {
    baseMultiplier = 0.95;
  } else if (ageHours <= 72) {
    baseMultiplier = 0.85;
  } else if (ageHours <= 168) {
    baseMultiplier = 0.70;
  } else {
    baseMultiplier = 0.60;
  }

  // Historical-low protection: Verified all-time record lows receive +0.08 retention resilience
  const effectiveMultiplier = deal.is_verified_low
    ? Math.min(1.0, baseMultiplier + 0.08)
    : baseMultiplier;

  return rawScore * effectiveMultiplier;
}
