import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import * as auth from '../services/auth';
type AuthContextValue = {
  user: auth.AuthUser | null;
  hydrated: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (name: string, email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  completeOnboarding: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<auth.AuthUser | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    auth.restoreSession().then(setUser).finally(() => setHydrated(true));
  }, []);

  const signIn = async (email: string, password: string) => setUser(await auth.signIn(email, password));
  const signUp = async (name: string, email: string, password: string) => setUser(await auth.signUp(name, email, password));
  const completeOnboarding = async () => {
    await auth.completeOnboarding();
    setUser((current) => current ? { ...current, needsOnboarding: false } : current);
  };
  const signOut = async () => {
    await auth.signOut();
    setUser(null);
  };
  const value = useMemo(() => ({ user, hydrated, signIn, signUp, signOut, completeOnboarding }), [user, hydrated]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside AuthProvider');
  return value;
}
