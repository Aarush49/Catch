import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import { createClient, type SupabaseClient } from '@supabase/supabase-js';

// expo-secure-store has no web implementation; browsers keep the session in localStorage.
const webStorage = {
  getItem: async (key: string) => (typeof window === 'undefined' ? null : window.localStorage.getItem(key)),
  setItem: async (key: string, value: string) => { if (typeof window !== 'undefined') window.localStorage.setItem(key, value); },
  removeItem: async (key: string) => { if (typeof window !== 'undefined') window.localStorage.removeItem(key); },
};
const nativeStorage = {
  getItem: (key: string) => SecureStore.getItemAsync(key),
  setItem: (key: string, value: string) => SecureStore.setItemAsync(key, value),
  removeItem: (key: string) => SecureStore.deleteItemAsync(key),
};
const storage = Platform.OS === 'web' ? webStorage : nativeStorage;

let client: SupabaseClient | null = null;

export function getSupabase() {
  if (client) return client;
  const url = process.env.EXPO_PUBLIC_SUPABASE_URL;
  const key = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) throw new Error('Supabase is not configured. Add the URL and anon key to frontend/.env.');
  client = createClient(url, key, { auth: { storage, persistSession: true, autoRefreshToken: true, detectSessionInUrl: false } });
  return client;
}

export const demoMode = process.env.EXPO_PUBLIC_DEMO_MODE === 'true';
