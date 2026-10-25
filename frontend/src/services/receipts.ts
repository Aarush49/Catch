import { Platform } from 'react-native';
import type { Category, Receipt } from '../data/mock';
import { mockReceipts } from '../data/mock';
import { accessToken, isDemoSession } from './auth';
import { demoMode, getSupabase } from './supabase';

/** Illustrative kg CO2e per dollar spent, by category. */
export const carbonFactors: Record<Category, number> = { Groceries: .12, Dining: .16, Household: .1, Health: .07, Transport: .2, Other: .09 };
const carbon = (price: number, category: Category) => +(price * carbonFactors[category]).toFixed(2);
const category = (value?: string): Category => ['Groceries', 'Dining', 'Household', 'Health', 'Transport', 'Other'].includes(value || '') ? value as Category : 'Other';

const isUuid = (value: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
const receiptColumns = 'id,merchant,purchased_at,tax,total,receipt_items(id,position,name,quantity,price,category,carbon_kg_co2e)';
const today = () => new Date().toISOString().slice(0, 10);

function toReceipt(row: any): Receipt {
  const items = [...(row.receipt_items || [])].sort((a: any, b: any) => a.position - b.position).map((item: any) => {
    const cat = category(item.category);
    const quantity = Number(item.quantity || 1);
    const price = Number(item.price || 0);
    return { id: item.id, name: item.name, quantity, price, category: cat, carbon: item.carbon_kg_co2e == null ? carbon(price * quantity, cat) : Number(item.carbon_kg_co2e) };
  });
  return { id: row.id, merchant: row.merchant || 'Unknown store', date: row.purchased_at || today(), tax: Number(row.tax || 0), total: Number(row.total || 0), items };
}

export async function listReceipts(): Promise<Receipt[]> {
  if (demoMode) return mockReceipts;
  const { data, error } = await getSupabase().from('receipts').select(receiptColumns).order('purchased_at', { ascending: false }).order('created_at', { ascending: false });
  if (error) throw error;
  return (data || []).map(toReceipt);
}

// Creates a receipt, or replaces an already-saved one, in a single database transaction.
export async function saveReceipt(receipt: Receipt): Promise<Receipt> {
  if (demoMode) return receipt;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(receipt.date) || Number.isNaN(Date.parse(`${receipt.date}T12:00:00`))) throw new Error('Enter the date as YYYY-MM-DD.');
  const items = receipt.items.filter((item) => item.name.trim());
  if (items.some((item) => !(item.price >= 0) || !(item.quantity > 0))) throw new Error('Each item needs a price of 0 or more and a quantity above 0.');
  const supabase = getSupabase();
  const { data: id, error } = await supabase.rpc('save_receipt', { p_receipt: {
    id: isUuid(receipt.id) ? receipt.id : null,
    merchant: receipt.merchant.trim(),
    purchased_at: receipt.date,
    tax: Math.max(receipt.tax || 0, 0),
    items: items.map((item) => ({ name: item.name.trim(), quantity: item.quantity, price: item.price, category: item.category, carbon_kg_co2e: carbon(item.price * item.quantity, item.category) })),
  } });
  if (error) throw new Error(error.code === '42501' ? 'Your session expired. Please sign in again.' : error.message);
  const { data, error: readError } = await supabase.from('receipts').select(receiptColumns).eq('id', id).single();
  if (readError) throw readError;
  return toReceipt(data);
}

export async function deleteReceipt(id: string): Promise<void> {
  if (demoMode || !isUuid(id)) return;
  const { data, error } = await getSupabase().from('receipts').delete().eq('id', id).select('id');
  if (error) throw error;
  if (!data?.length) throw new Error('This receipt was already deleted or belongs to another account.');
}

export async function scanReceipt(uri: string): Promise<Receipt & { needsReview?: boolean; reviewReason?: string }> {
  if (demoMode || isDemoSession()) return { ...mockReceipts[0], id: `demo-${Date.now()}` };
  const apiUrl = process.env.EXPO_PUBLIC_API_URL;
  if (!apiUrl) throw new Error('Receipt scanning is not configured. Add EXPO_PUBLIC_API_URL to frontend/.env.');
  const token = await accessToken();
  if (!token) throw new Error('Your session expired. Please sign in again.');
  const body = new FormData();
  if (Platform.OS === 'web') body.append('file', await (await fetch(uri)).blob(), 'receipt.jpg');
  else body.append('file', { uri, name: 'receipt.jpg', type: 'image/jpeg' } as any);
  const response = await fetch(`${apiUrl}/receipts/scan`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'Could not read this receipt.');
  const items = (payload.items || []).map((item: any, index: number) => { const cat = category(item.category); const quantity = Math.max(Number(item.quantity || 1), 1); const lineTotal = Number(item.price || 0); return { id: `scan-${index}`, name: item.name || 'Unreadable item', quantity, price: lineTotal / quantity, category: cat, carbon: carbon(lineTotal, cat), confidence: payload.needs_review }; });
  const subtotal = items.reduce((sum: number, item: any) => sum + item.price * item.quantity, 0);
  return { id: `scan-${Date.now()}`, merchant: payload.merchant || 'Unknown store', date: payload.purchased_at || new Date().toISOString().slice(0, 10), tax: Number(payload.tax || 0), total: Number(payload.total ?? subtotal + Number(payload.tax || 0)), items, needsReview: payload.needs_review, reviewReason: payload.review_reason };
}

