import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { Receipt } from '../data/mock';
import { listReceipts, saveReceipt as persistReceipt } from '../services/receipts';
import { useAuth } from './AuthProvider';

type TallyContextValue = {
  receipts: Receipt[];
  setReceipts: React.Dispatch<React.SetStateAction<Receipt[]>>;
  saveReceipt: (receipt: Receipt) => Promise<Receipt>;
  shopping: string[];
  setShopping: React.Dispatch<React.SetStateAction<string[]>>;
  ready: boolean;
  reset: () => Promise<void>;
};
const TallyContext = createContext<TallyContextValue | null>(null);

export function TallyProvider({ children }: { children: React.ReactNode }) {
  const { user, hydrated } = useAuth();
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [shopping, setShopping] = useState<string[]>([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!hydrated) return;
    if (!user) { setReceipts([]); setReady(true); return; }
    setReady(false);
    (async () => {
      const cached = await AsyncStorage.getItem('tally-receipts');
      if (cached) setReceipts(JSON.parse(cached));
      const remote = await listReceipts();
      setReceipts(remote);
      await AsyncStorage.setItem('tally-receipts', JSON.stringify(remote));
    })().catch(() => {}).finally(() => setReady(true));
  }, [hydrated, user?.id, user?.email]);

  useEffect(() => { if (ready) AsyncStorage.setItem('tally-shopping', JSON.stringify(shopping)); }, [ready, shopping]);
  const saveReceipt = async (receipt: Receipt) => {
    const saved = await persistReceipt(receipt);
    setReceipts((all) => [saved, ...all.filter((item) => item.id !== receipt.id)]);
    return saved;
  };
  const reset = async () => { setReceipts([]); setShopping([]); await AsyncStorage.multiSet([['tally-receipts', '[]'], ['tally-shopping', '[]']]); };
  const value = useMemo(() => ({ receipts, setReceipts, saveReceipt, shopping, setShopping, ready, reset }), [receipts, shopping, ready]);
  return <TallyContext.Provider value={value}>{children}</TallyContext.Provider>;
}

export function useTally() {
  const value = useContext(TallyContext);
  if (!value) throw new Error('useTally must be used inside TallyProvider');
  return value;
}
