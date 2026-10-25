import type { Category, Receipt } from '../data/mock';
import { accessToken, isDemoSession } from './auth';
import { demoMode, getSupabase } from './supabase';

export type ShoppingItem = { id: string; name: string; price: number | null; category: Category; completed: boolean };
export type ShoppingAlternative = {
  title: string; price: number; source: string | null; rating: number | null; link: string; thumbnail: string | null;
  match_type: 'exact_title_match' | 'similar_alternative'; potential_savings: number; potential_savings_percent: number;
  // Extra listing details from the same Google Shopping search; any of them may be missing.
  reviews?: number | null; old_price?: number | null; unit_price?: string | null; tag?: string | null;
  delivery?: string | null; nearby?: string | null;
};
export type ComparedItem = { item_id: string; name: string; original_price: number | null; alternatives: ShoppingAlternative[]; potential_savings: number; error: string | null };
export type ShoppingComparison = { items: ComparedItem[]; total_potential_savings: number };

// shopping_items.category and bank purchase categories use the backend's vocabulary (backend/models.py ExpenseCategory).
const toDb: Record<Category, string> = { Groceries: 'groceries', Dining: 'restaurant', Household: 'household', Health: 'health', Transport: 'transportation', Other: 'other' };
export const categoryFromDb = (value?: string): Category => (Object.keys(toDb) as Category[]).find((key) => toDb[key] === value) ?? 'Other';
const fromDb = categoryFromDb;
const columns = 'id,name,price,category,completed';
const toItem = (row: any): ShoppingItem => ({ id: row.id, name: row.name, price: row.price == null ? null : Number(row.price), category: fromDb(row.category), completed: Boolean(row.completed) });

const normalize = (name: string) => name.trim().toLowerCase().replace(/\s+/g, ' ');

export function validPrice(value: number | null) {
  return value === null || (Number.isFinite(value) && value > 0);
}

/** The unit price and category the user last paid for an item with this name, from saved receipts. */
export function lastPurchase(receipts: Receipt[], name: string) {
  const wanted = normalize(name);
  const newestFirst = [...receipts].sort((a, b) => b.date.localeCompare(a.date));
  for (const receipt of newestFirst) {
    const item = receipt.items.find((line) => normalize(line.name) === wanted && line.price > 0);
    if (item) return { price: +item.price.toFixed(2), category: item.category, merchant: receipt.merchant, date: receipt.date };
  }
  return null;
}

export async function listShoppingItems(): Promise<ShoppingItem[]> {
  const { data, error } = await getSupabase().from('shopping_items').select(columns).order('created_at', { ascending: true });
  if (error) throw error;
  return (data || []).map(toItem);
}

export async function addShoppingItem(input: { name: string; price: number | null; category: Category }): Promise<ShoppingItem> {
  const name = input.name.trim();
  if (!name) throw new Error('Enter an item name.');
  if (!validPrice(input.price)) throw new Error('Enter a price above $0, or leave it empty.');
  // Generic names rarely match a listing title exactly, so allow similar listings; Compare labels each match.
  const { data, error } = await getSupabase().from('shopping_items')
    .insert({ name, price: input.price, category: toDb[input.category], allow_lower_quality: true })
    .select(columns).single();
  if (error) throw error;
  return toItem(data);
}

export async function updateShoppingItem(id: string, patch: Partial<Pick<ShoppingItem, 'name' | 'price' | 'completed'>>): Promise<ShoppingItem> {
  if (patch.name !== undefined && !patch.name.trim()) throw new Error('Enter an item name.');
  if (patch.price !== undefined && !validPrice(patch.price)) throw new Error('Enter a price above $0, or leave it empty.');
  const { data, error } = await getSupabase().from('shopping_items')
    .update({ ...patch, ...(patch.name !== undefined ? { name: patch.name.trim() } : {}) })
    .eq('id', id).select(columns).single();
  if (error) throw error;
  return toItem(data);
}

export async function deleteShoppingItem(id: string): Promise<void> {
  const { error } = await getSupabase().from('shopping_items').delete().eq('id', id);
  if (error) throw error;
}

export async function recordSwap(swap: { originalName: string; replacementName: string; savings: number }): Promise<void> {
  const { error } = await getSupabase().from('accepted_recommendations')
    .insert({ original_name: swap.originalName, replacement_name: swap.replacementName, savings: swap.savings });
  if (error) throw error;
}

/** Ask the backend to search Google Shopping (SerpAPI) for every unchecked, priced list item. */
export async function compareShoppingList(): Promise<ShoppingComparison> {
  if (demoMode || isDemoSession()) throw new Error('Price comparison needs a signed-in account; it is not available in demo mode.');
  const apiUrl = process.env.EXPO_PUBLIC_API_URL;
  if (!apiUrl) throw new Error('Price comparison is not configured. Add EXPO_PUBLIC_API_URL to frontend/.env.');
  const token = await accessToken();
  if (!token) throw new Error('Your session expired. Please sign in again.');
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/api/shopping-list/done`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
  } catch {
    throw new Error('Could not reach the Catch server. Check that the backend is running and EXPO_PUBLIC_API_URL is correct.');
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : 'Price comparison failed. Please try again.');
  return payload as ShoppingComparison;
}
