import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { mockReceipts, type Category, type Receipt } from '../data/mock';
import { deleteReceipt as removeReceipt, listReceipts, saveReceipt as persistReceipt } from '../services/receipts';
import { addShoppingItem as insertShoppingItem, deleteShoppingItem, listShoppingItems, updateShoppingItem as patchShoppingItem, type ShoppingItem } from '../services/shopping';
import { useAuth } from './AuthProvider';

type ShoppingPatch = Partial<Pick<ShoppingItem, 'name' | 'price' | 'completed'>>;
type TallyContextValue = {
  receipts: Receipt[];
  setReceipts: React.Dispatch<React.SetStateAction<Receipt[]>>;
  saveReceipt: (receipt: Receipt) => Promise<Receipt>;
  deleteReceipt: (id: string) => Promise<void>;
  shopping: ShoppingItem[];
  addShoppingItem: (item: { name: string; price: number | null; category: Category }) => Promise<ShoppingItem>;
  updateShoppingItem: (id: string, patch: ShoppingPatch) => Promise<ShoppingItem>;
  removeShoppingItem: (id: string) => Promise<void>;
  refreshShopping: () => Promise<void>;
  ready: boolean;
  reset: () => Promise<void>;
};
const TallyContext = createContext<TallyContextValue | null>(null);
const receiptsKey = (userId: string) => `tally-receipts:${userId}`;
const shoppingKey = (userId: string) => `tally-shopping-items:${userId}`;
const demoShopping = (): ShoppingItem[] => [
  { id: 'demo-1', name: 'Oat milk', price: 4.19, category: 'Groceries', completed: false },
  { id: 'demo-2', name: 'Sourdough loaf', price: 5.5, category: 'Groceries', completed: false },
  { id: 'demo-3', name: 'Avocados (3 ct)', price: 4.29, category: 'Groceries', completed: false },
];

export function TallyProvider({ children }: { children: React.ReactNode }) {
  const { user, hydrated } = useAuth();
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [shopping, setShopping] = useState<ShoppingItem[]>([]);
  const [ready, setReady] = useState(false);
  // The user whose data is currently in state; caches are only written for that user.
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const userId = user?.id;

  // Earlier builds cached under shared keys, then cached the list as plain names.
  useEffect(() => { AsyncStorage.multiRemove(['tally-receipts', 'tally-shopping']).catch(() => {}); }, []);

  useEffect(() => {
    if (!hydrated) return;
    setLoadedFor(null); setReceipts([]); setShopping([]);
    if (!userId) { setReady(true); return; }
    if (userId === 'demo') { setReceipts(mockReceipts); setShopping(demoShopping()); setReady(true); return; }
    let active = true;
    setReady(false);
    AsyncStorage.removeItem(`tally-shopping:${userId}`).catch(() => {});
    (async () => {
      const cached = await Promise.race([
        AsyncStorage.multiGet([receiptsKey(userId), shoppingKey(userId)]),
        new Promise<null>((resolve) => setTimeout(() => resolve(null), 1500)),
      ]);
      if (!active) return;
      if (cached) {
        const [cachedReceipts, cachedShopping] = cached.map(([, value]) => value);
        if (cachedReceipts) setReceipts(JSON.parse(cachedReceipts));
        if (cachedShopping) setShopping(JSON.parse(cachedShopping));
        setLoadedFor(userId);
      }
      setReady(true);
      const [remoteReceipts, remoteShopping] = await Promise.allSettled([listReceipts(), listShoppingItems()]);
      if (!active) return;
      // Keep this user's cached copy of whichever request failed (e.g. while offline).
      if (remoteReceipts.status === 'fulfilled') setReceipts(remoteReceipts.value);
      if (remoteShopping.status === 'fulfilled') setShopping(remoteShopping.value);
      if (remoteReceipts.status === 'fulfilled' && remoteShopping.status === 'fulfilled') setLoadedFor(userId);
    })().catch(() => {}).finally(() => { if (active) setReady(true); });
    return () => { active = false; };
  }, [hydrated, userId]);

  useEffect(() => { if (loadedFor && loadedFor === userId) AsyncStorage.setItem(receiptsKey(loadedFor), JSON.stringify(receipts)); }, [loadedFor, receipts, userId]);
  useEffect(() => { if (loadedFor && loadedFor === userId) AsyncStorage.setItem(shoppingKey(loadedFor), JSON.stringify(shopping)); }, [loadedFor, shopping, userId]);

  const saveReceipt = async (receipt: Receipt) => {
    const saved = userId === 'demo' ? receipt : await persistReceipt(receipt);
    setReceipts((all) => all.some((item) => item.id === receipt.id)
      ? all.map((item) => item.id === receipt.id ? saved : item)
      : [saved, ...all]);
    return saved;
  };
  const deleteReceipt = async (id: string) => {
    if (userId !== 'demo') await removeReceipt(id);
    setReceipts((all) => all.filter((item) => item.id !== id));
  };

  const addShoppingItem = async (item: { name: string; price: number | null; category: Category }) => {
    const saved = userId === 'demo'
      ? { id: `demo-${Date.now()}`, name: item.name.trim(), price: item.price, category: item.category, completed: false }
      : await insertShoppingItem(item);
    setShopping((all) => [...all, saved]);
    return saved;
  };
  const updateShoppingItem = async (id: string, patch: ShoppingPatch) => {
    const current = shopping.find((item) => item.id === id);
    if (!current) throw new Error('That item is no longer on your list.');
    const saved = userId === 'demo' ? { ...current, ...patch } : await patchShoppingItem(id, patch);
    setShopping((all) => all.map((item) => item.id === id ? saved : item));
    return saved;
  };
  const removeShoppingItem = async (id: string) => {
    if (userId !== 'demo') await deleteShoppingItem(id);
    setShopping((all) => all.filter((item) => item.id !== id));
  };
  const refreshShopping = async () => {
    if (!userId || userId === 'demo') return;
    setShopping(await listShoppingItems());
  };

  const reset = async () => { setReceipts([]); setShopping([]); if (!userId || userId === 'demo') return; await AsyncStorage.multiSet([[receiptsKey(userId), '[]'], [shoppingKey(userId), '[]']]); };
  const value = useMemo(() => ({ receipts, setReceipts, saveReceipt, deleteReceipt, shopping, addShoppingItem, updateShoppingItem, removeShoppingItem, refreshShopping, ready, reset }), [receipts, shopping, ready, userId]);
  return <TallyContext.Provider value={value}>{children}</TallyContext.Provider>;
}

export function useTally() {
  const value = useContext(TallyContext);
  if (!value) throw new Error('useTally must be used inside TallyProvider');
  return value;
}
