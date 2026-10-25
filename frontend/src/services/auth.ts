import type { Session } from '@supabase/supabase-js';
import { demoMode, getSupabase } from './supabase';

export type AuthUser = { id?: string; email: string; name?: string; needsOnboarding?: boolean };
const demoUser = (email: string, name?: string, needsOnboarding = false): AuthUser => ({ id: 'demo', email, name, needsOnboarding });
let demoSessionActive = false;
export const isDemoSession = () => demoSessionActive;
export function startDemoSession(): AuthUser { demoSessionActive = true; return demoUser('demo@catch.local', 'Demo user'); }

export function sessionUser(session: Session | null): AuthUser | null {
  if (!session?.user.email) return null;
  return { id: session.user.id, email: session.user.email, name: session.user.user_metadata.display_name, needsOnboarding: Boolean(session.user.user_metadata.needs_onboarding) };
}

export async function restoreSession() {
  if (demoMode) return null;
  try {
    const result = await Promise.race([
      getSupabase().auth.getSession(),
      new Promise<never>((_, reject) => setTimeout(() => reject(new Error('Session restore timed out')), 2500)),
    ]);
    return sessionUser(result.data.session);
  } catch { return null; }
}

export async function signIn(email: string, password: string) {
  demoSessionActive = false;
  if (demoMode) return demoUser(email);
  const { data, error } = await getSupabase().auth.signInWithPassword({ email, password });
  if (error) throw error;
  return sessionUser(data.session)!;
}

export async function signUp(name: string, email: string, password: string) {
  demoSessionActive = false;
  if (demoMode) return demoUser(email, name, true);
  const { data, error } = await getSupabase().auth.signUp({ email, password, options: { data: { display_name: name, needs_onboarding: true } } });
  if (error) throw error;
  if (!data.session) throw new Error('Check your email to confirm your account, then sign in.');
  return sessionUser(data.session)!;
}

export async function completeOnboarding() {
  if (demoMode) return;
  const { error } = await getSupabase().auth.updateUser({ data: { needs_onboarding: false } });
  if (error) throw error;
}

export async function signOut(skipRemote = false) {
  demoSessionActive = false;
  if (!demoMode && !skipRemote) {
    const { error } = await getSupabase().auth.signOut();
    if (error) throw error;
  }
}

export async function accessToken() {
  if (demoMode || demoSessionActive) return 'demo';
  return (await getSupabase().auth.getSession()).data.session?.access_token ?? null;
}





