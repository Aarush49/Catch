import { Category, ReceiptItem } from '../types';
import { rateForCategory } from './categoryRates';

export const factors: Record<Category, number> = { dining: .18, grocery: .09, transport: .24, shopping: .14, entertainment: .08, utilities: .32, other: .12 };
export const estimateCarbon = (amount: number, category: Category = 'other') => amount * (factors[category] ?? factors.other);

/**
 * Future value of an amount after `years` at the category-specific growth rate.
 * Rate is sourced from categoryRates.ts (illustrative long-run estimates, not predictions).
 * Falls back to the default rate for unknown categories.
 */
export const futureValue = (amount: number, years = 30, category: Category | string = 'other') =>
  amount * (1 + rateForCategory(category)) ** years;

/**
 * Weighted-average annual growth rate for a receipt, computed from its line items.
 * Item-level categories take priority (each item contributes proportionally by price).
 * Falls back to the default rate when items is empty.
 */
export const receiptRate = (items: ReceiptItem[]): number => {
  const total = items.reduce((s, i) => s + Number(i.price || 0), 0);
  if (!total) return rateForCategory('other');
  return items.reduce((s, i) => s + rateForCategory(i.category) * Number(i.price || 0), 0) / total;
};

/**
 * Year-by-year timeline for two spending scenarios using the same category-aware rate.
 * Pass `category` for a single-category purchase, or use `buildTimelineFromItems` for
 * multi-category receipts (item-level categories take priority).
 */
export const buildTimeline = (original: number, changed: number, years = 30, category: Category | string = 'other') =>
  Array.from({ length: years + 1 }, (_, year) => ({
    year,
    original: futureValue(original, year, category),
    changed: futureValue(changed, year, category),
  }));

/**
 * Like buildTimeline but derives the growth rate from a receipt's item categories.
 * Both `original` and `changed` scenarios use the same weighted rate so the gap is meaningful.
 */
export const buildTimelineFromItems = (original: number, changed: number, items: ReceiptItem[], years = 30) => {
  const rate = receiptRate(items);
  return Array.from({ length: years + 1 }, (_, year) => ({
    year,
    original: original * (1 + rate) ** year,
    changed: changed * (1 + rate) ** year,
  }));
};

export const receiptTotal = (items: { price: number }[]) => items.reduce((sum, item) => sum + Number(item.price || 0), 0);
export const receiptCarbon = (items: { price: number; category: Category }[]) => items.reduce((sum, item) => sum + estimateCarbon(item.price, item.category), 0);

/**
 * Category-aware future value of an entire receipt.
 * Each item is grown at its own category rate (item-level categories take priority).
 */
export const receiptFutureValue = (items: ReceiptItem[], years = 30): number =>
  items.reduce((sum, item) => sum + futureValue(Number(item.price || 0), years, item.category), 0);

export const currency = (value: number, digits = 0) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: digits }).format(value);
