import { useCallback, useState } from 'react';
import { useFocusEffect } from 'expo-router';
import { listBankTransactions, type BankTransaction } from '../services/bank';
import { useAuth } from './AuthProvider';

/** The signed-in user's imported bank rows, reloaded each time the screen comes into focus. */
export function useBankTransactions() {
  const { user } = useAuth();
  const canBank = !!user && user.id !== 'demo';
  const [rows, setRows] = useState<BankTransaction[]>([]);
  const [error, setError] = useState('');
  useFocusEffect(useCallback(() => {
    if (!canBank) { setRows([]); return; }
    let active = true;
    listBankTransactions().then(
      (loaded) => { if (active) { setRows(loaded); setError(''); } },
      () => { if (active) setError('Could not load bank activity. Try Refresh in your profile.'); },
    );
    return () => { active = false; };
  }, [canBank]));
  return { rows, error, canBank };
}
