import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

type User = { email: string; name?: string; needsOnboarding?: boolean };
type AuthContextValue = {
  user: User | null;
  hydrated: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (name: string, email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  completeOnboarding: () => Promise<void>;
};

const SESSION_KEY = 'catch-session';
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(SESSION_KEY)
      .then((session) => setUser(session ? JSON.parse(session) : null))
      .finally(() => setHydrated(true));
  }, []);

  const save = async (nextUser: User) => {
    await AsyncStorage.setItem(SESSION_KEY, JSON.stringify(nextUser));
    setUser(nextUser);
  };
  const signIn = async (email: string, _password: string) => save({ email, needsOnboarding: false });
  const signUp = async (name: string, email: string, _password: string) => save({ name, email, needsOnboarding: true });
  const completeOnboarding = async () => {
    if (user) await save({ ...user, needsOnboarding: false });
  };
  const signOut = async () => {
    setUser(null);
    await AsyncStorage.removeItem(SESSION_KEY);
  };
  const value = useMemo(() => ({ user, hydrated, signIn, signUp, signOut, completeOnboarding }), [user, hydrated]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside AuthProvider');
  return value;
}
