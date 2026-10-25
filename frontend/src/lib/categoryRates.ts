import { Category } from '../types';

/**
 * Illustrative long-run annual growth rates by category.
 * These are estimates for how spending power in each category compounds
 * over time, NOT investment return predictions.
 *
 * Rates reflect historical inflation trends and supply/demand dynamics:
 *   ~5.0x over 30 yrs = 5.5%  (fuel / energy / utilities – scarce, volatile)
 *   ~4.3x over 30 yrs = 5.0%  (healthcare / education)
 *   ~3.2x over 30 yrs = 4.0%  (housing / rent)
 *   ~2.8x over 30 yrs = 3.5%  (groceries / dining)
 *   ~2.4x over 30 yrs = 3.0%  (default / other)
 *   ~1.8x over 30 yrs = 2.0%  (apparel / household goods)
 *   ~1.6x over 30 yrs = 1.5%  (subscriptions / digital)
 *   ~1.0x over 30 yrs = 0.0%  (electronics / tech – prices fall over time)
 */
export const CATEGORY_RATES: Record<Category, number> = {
  // Fuel / energy / utilities – scarce, volatile (~5.0x)
  utilities: 0.055,
  // Transport overlaps heavily with fuel costs
  transport: 0.055,
  // Groceries / dining (~2.8x)
  grocery: 0.035,
  dining: 0.035,
  // Apparel / household goods – more substitutable (~1.8x)
  shopping: 0.02,
  // Subscriptions / digital – competition keeps prices low (~1.6x)
  entertainment: 0.015,
  // Default / other (~2.4x)
  other: 0.03,
};

/** Fallback rate for any category not found in the table. */
export const DEFAULT_RATE = CATEGORY_RATES.other;

/** Return the annual growth rate for a given category. */
export function rateForCategory(category: Category | string | undefined): number {
  if (!category) return DEFAULT_RATE;
  return (CATEGORY_RATES as Record<string, number>)[category] ?? DEFAULT_RATE;
}
