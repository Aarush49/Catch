import AsyncStorage from '@react-native-async-storage/async-storage';
import { isDemoSession } from './auth';
import { demoMode, getSupabase } from './supabase';

export type PredictMode = 'Buy this' | 'Different price' | 'Skip it';
export type PredictScenario = { mode: PredictMode; cost: number; frequency: number; change: number; years: number };
export type PredictionRequest = { amount: number; alternative_amount?: number; times_per_month: number; years: number };
export type Prediction = {
  years: number; annual_return: number; explanation: string; explanation_source: 'gemini' | 'fallback';
  recurring: {
    times_per_month: number; monthly_savings: number; annual_spend: number; annual_alternative_spend: number;
    total_saved: number; future_value_if_saved: number; future_savings: number;
  };
};
export type SavingsGoal = PredictScenario & { futureSavings: number; monthlySavings: number; savedAt: string };

const cents = (value: number) => Math.round(value * 100) / 100;
export const changedPrice = (scenario: PredictScenario) => cents(scenario.cost * (1 + scenario.change / 100));

/** What the backend compares for each mode. A price rise is projected as the saving from keeping today's price. */
export function predictionRequest(scenario: PredictScenario): PredictionRequest {
  const base = { times_per_month: scenario.frequency, years: scenario.years };
  if (scenario.mode !== 'Different price') return { ...base, amount: scenario.cost };
  const newPrice = changedPrice(scenario);
  return newPrice > scenario.cost
    ? { ...base, amount: newPrice, alternative_amount: scenario.cost }
    : { ...base, amount: scenario.cost, alternative_amount: newPrice };
}

/** Future value of the money a scenario keeps; POST /api/predictions needs no login. */
export async function predictSavings(request: PredictionRequest, signal?: AbortSignal): Promise<Prediction> {
  const apiUrl = process.env.EXPO_PUBLIC_API_URL;
  if (!apiUrl) throw new Error('Projections are not configured. Add EXPO_PUBLIC_API_URL to frontend/.env.');
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/api/predictions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request), signal });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new Error('Could not reach the Catch server. Check that the backend is running and EXPO_PUBLIC_API_URL is correct.');
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : 'The projection failed. Please try again.');
  return payload as Prediction;
}

// Signed-in goals live in Supabase auth user_metadata so they follow the account; demo goals stay on this device.
const localGoalKey = 'catch-predict-goal:demo';
const localOnly = () => demoMode || isDemoSession();
const isGoal = (value: any): value is SavingsGoal => Boolean(value) && typeof value.futureSavings === 'number' && typeof value.years === 'number' && typeof value.mode === 'string';

export async function loadGoal(): Promise<SavingsGoal | null> {
  if (localOnly()) {
    const stored = await AsyncStorage.getItem(localGoalKey);
    const goal = stored ? JSON.parse(stored) : null;
    return isGoal(goal) ? goal : null;
  }
  const { data, error } = await getSupabase().auth.getUser();
  if (error) throw error;
  const goal = data.user?.user_metadata?.predict_goal;
  return isGoal(goal) ? goal : null;
}

export async function saveGoal(goal: SavingsGoal | null): Promise<void> {
  if (localOnly()) {
    if (goal) await AsyncStorage.setItem(localGoalKey, JSON.stringify(goal));
    else await AsyncStorage.removeItem(localGoalKey);
    return;
  }
  const { error } = await getSupabase().auth.updateUser({ data: { predict_goal: goal } });
  if (error) throw error;
}
