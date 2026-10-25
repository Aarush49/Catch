import { accessToken, isDemoSession } from './auth';
import { demoMode, getSupabase } from './supabase';

/** type is purchase, withdrawal, deposit, income (paychecks), transfer, savings (moved into Catch savings) or bill (upcoming). */
export type BankTransaction = { id: string; type: string; amount: number; date: string; description: string; category: string };
export type BankLink = { accountId: string; linkedAt: string };
export type BankImport = { count: number; created?: boolean };
export type SavingsMove = { moved: number; savingsTotal: number };

/** Money that left the account. Transfers are excluded: the ones Catch makes are moves into savings. */
export const isBankSpending = (txn: BankTransaction) => txn.type === 'purchase' || txn.type === 'withdrawal';
/** Money that came in: paychecks (imported as "income") and other deposits. */
export const isBankIncome = (txn: BankTransaction) => txn.type === 'income' || txn.type === 'deposit';
export const isBill = (txn: BankTransaction) => txn.type === 'bill';
export const savingsTotal = (rows: BankTransaction[]) => rows.filter((txn) => txn.type === 'savings').reduce((sum, txn) => sum + txn.amount, 0);

const signedIn = () => !demoMode && !isDemoSession();

// Bank rows are read-only for users (RLS select policy); only the backend imports them.
export async function getBankLink(): Promise<BankLink | null> {
  if (!signedIn()) return null;
  const { data, error } = await getSupabase().from('linked_accounts').select('account_id,linked_at').maybeSingle();
  if (error) throw error;
  return data ? { accountId: data.account_id, linkedAt: data.linked_at } : null;
}

export async function listBankTransactions(): Promise<BankTransaction[]> {
  if (!signedIn()) return [];
  const { data, error } = await getSupabase().from('transactions')
    .select('id,transaction_type,amount,date,description,category')
    .eq('source', 'nessie').order('date', { ascending: false });
  if (error) throw error;
  return (data || []).map((row: any) => ({
    id: row.id, type: row.transaction_type, amount: Number(row.amount), date: row.date,
    description: row.description || row.transaction_type, category: row.category,
  }));
}

async function callBank(path: string, method: 'GET' | 'POST', body?: object): Promise<any> {
  if (!signedIn()) throw new Error('Connecting a bank needs a signed-in account; it is not available in demo mode.');
  const apiUrl = process.env.EXPO_PUBLIC_API_URL;
  if (!apiUrl) throw new Error('Bank connection is not configured. Add EXPO_PUBLIC_API_URL to frontend/.env.');
  const token = await accessToken();
  if (!token) throw new Error('Your session expired. Please sign in again.');
  let response: Response;
  try {
    response = await fetch(`${apiUrl}${path}`, {
      method,
      headers: { Authorization: `Bearer ${token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
  } catch {
    throw new Error('Could not reach the Catch server. Check that the backend is running and EXPO_PUBLIC_API_URL is correct.');
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : 'The bank request failed. Please try again.');
  return payload;
}

const toImport = (payload: any): BankImport => ({ count: Number(payload.count) || 0, created: payload.created });

/**
 * Creates and links a sandbox checking account with sample activity and bills. If one is already linked it
 * re-imports it instead (adding bills to a demo account made before bills existed), so it doubles as Refresh.
 */
export const connectDemoBank = async () => toImport(await callBank('/api/nessie/demo-bank', 'POST'));
export const refreshBank = connectDemoBank;

/** Moves money from checking into Catch savings. The bank sandbox keeps whole dollars, so it rounds to the nearest dollar. */
export async function moveToSavings(amount: number, description: string): Promise<SavingsMove> {
  const payload = await callBank('/api/nessie/savings', 'POST', { amount: +amount.toFixed(2), description: description.slice(0, 200) });
  return { moved: Number(payload.moved) || 0, savingsTotal: Number(payload.savings_total) || 0 };
}
