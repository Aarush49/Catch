import type { Category, Receipt } from '../data/mock';
import { mockReceipts } from '../data/mock';
import { accessToken, isDemoSession } from './auth';
import { demoMode, getSupabase } from './supabase';

const factors: Record<Category, number> = { Groceries: .12, Dining: .16, Household: .1, Health: .07, Transport: .2, Other: .09 };
const carbon = (price: number, category: Category) => +(price * factors[category]).toFixed(2);
const category = (value?: string): Category => ['Groceries', 'Dining', 'Household', 'Health', 'Transport', 'Other'].includes(value || '') ? value as Category : 'Other';

export async function listReceipts(): Promise<Receipt[]> {
  if (demoMode) return mockReceipts;
  const { data, error } = await getSupabase().from('receipts').select('id,merchant,purchased_at,subtotal,tax,total,receipt_items(id,name,quantity,price,category)').order('purchased_at', { ascending: false });
  if (error) throw error;
  return (data || []).map((row: any) => ({ id: row.id, merchant: row.merchant || 'Unknown store', date: row.purchased_at || new Date().toISOString().slice(0, 10), tax: Number(row.tax || 0), total: Number(row.total || 0), items: (row.receipt_items || []).map((item: any) => ({ id: item.id, name: item.name, quantity: Number(item.quantity || 1), price: Number(item.price || 0), category: category(item.category), carbon: carbon(Number(item.price || 0) * Number(item.quantity || 1), category(item.category)) })) }));
}

export async function saveReceipt(receipt: Receipt): Promise<Receipt> {
  if (demoMode) return receipt;
  const supabase = getSupabase();
  const { data: auth } = await supabase.auth.getUser();
  if (!auth.user) throw new Error('Your session expired. Please sign in again.');
  const subtotal = receipt.items.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const { data, error } = await supabase.from('receipts').insert({ user_id: auth.user.id, merchant: receipt.merchant, purchased_at: receipt.date, subtotal, tax: receipt.tax, total: subtotal + receipt.tax }).select('id').single();
  if (error) throw error;
  const { error: itemError } = await supabase.from('receipt_items').insert(receipt.items.map((item) => ({ receipt_id: data.id, name: item.name, quantity: item.quantity, price: item.price, category: item.category })));
  if (itemError) { await supabase.from('receipts').delete().eq('id', data.id); throw itemError; }
  return { ...receipt, id: data.id, total: +(subtotal + receipt.tax).toFixed(2) };
}

export async function scanReceipt(uri: string): Promise<Receipt & { needsReview?: boolean; reviewReason?: string }> {
  if (demoMode || isDemoSession()) return { ...mockReceipts[0], id: `demo-${Date.now()}` };
  const apiUrl = process.env.EXPO_PUBLIC_API_URL;
  if (!apiUrl) throw new Error('Receipt scanning is not configured. Add EXPO_PUBLIC_API_URL to frontend/.env.');
  const token = await accessToken();
  if (!token) throw new Error('Your session expired. Please sign in again.');
  const body = new FormData();
  body.append('file', { uri, name: 'receipt.jpg', type: 'image/jpeg' } as any);
  const response = await fetch(`${apiUrl}/receipts/scan`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || 'Could not read this receipt.');
  const items = (payload.items || []).map((item: any, index: number) => { const cat = category(item.category); const quantity = Math.max(Number(item.quantity || 1), 1); const lineTotal = Number(item.price || 0); return { id: `scan-${index}`, name: item.name || 'Unreadable item', quantity, price: lineTotal / quantity, category: cat, carbon: carbon(lineTotal, cat), confidence: payload.needs_review }; });
  const subtotal = items.reduce((sum: number, item: any) => sum + item.price * item.quantity, 0);
  return { id: `scan-${Date.now()}`, merchant: payload.merchant || 'Unknown store', date: payload.purchased_at || new Date().toISOString().slice(0, 10), tax: Number(payload.tax || 0), total: Number(payload.total ?? subtotal + Number(payload.tax || 0)), items, needsReview: payload.needs_review, reviewReason: payload.review_reason };
}

