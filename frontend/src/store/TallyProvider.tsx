import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { mockReceipts, type Receipt } from '../data/mock';
import { deleteReceipt as removeReceipt, listReceipts, saveReceipt as persistReceipt } from '../services/receipts';
import { useAuth } from './AuthProvider';

type TallyContextValue = {
  receipts: Receipt[];
  setReceipts: React.Dispatch<React.SetStateAction<Receipt[]>>;
  saveReceipt: (receipt: Receipt) => Promise<Receipt>;
  deleteReceipt: (id: string) => Promise<void>;
  shopping: string[];
  setShopping: React.Dispatch<React.SetStateAction<string[]>>;
  ready: boolean;
  reset: () => Promise<void>;
};
const TallyContext = createContext<TallyContextValue | null>(null);
const receiptsKey = (userId: string) => `tally-receipts:${userId}`;
const shoppingKey = (userId: string) => `tally-shopping:${userId}`;

export function TallyProvider({ children }: { children: React.ReactNode }) {
  const { user, hydrated } = useAuth();
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [shopping, setShopping] = useState<string[]>([]);
  const [ready, setReady] = useState(false);
  // The user whose data is currently in state; caches are only written for that user.
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const userId = user?.id;

  // Earlier builds cached every account under these shared keys.
  useEffect(() => { AsyncStorage.multiRemove(['tally-receipts', 'tally-shopping']).catch(() => {}); }, []);

  useEffect(() => {
    if (!hydrated) return;
    setLoadedFor(null); setReceipts([]); setShopping([]);
    if (!userId) { setReady(true); return; }
    if (userId === 'demo') { setReceipts(mockReceipts); setShopping(['Oat milk', 'Sourdough loaf', 'Avocados']); setReady(true); return; }
    let active = true;
    setReady(false);
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
      const remote = await listReceipts();
      if (active) { setReceipts(remote); setLoadedFor(userId); }
    })().catch(() => { /* Keep this user's cached receipts while offline. */ }).finally(() => { if (active) setReady(true); });
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
  const reset = async () => { setReceipts([]); setShopping([]); if (!userId || userId === 'demo') return; await AsyncStorage.multiSet([[receiptsKey(userId), '[]'], [shoppingKey(userId), '[]']]); };
  const value = useMemo(() => ({ receipts, setReceipts, saveReceipt, deleteReceipt, shopping, setShopping, ready, reset }), [receipts, shopping, ready, userId]);
  return <TallyContext.Provider value={value}>{children}</TallyContext.Provider>;
}

export function useTally() {
  const value = useContext(TallyContext);
  if (!value) throw new Error('useTally must be used inside TallyProvider');
  return value;
}
