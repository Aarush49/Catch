import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, Pressable, Text, View } from 'react-native';
import { router } from 'expo-router';
import Slider from '@react-native-community/slider';
import { ArrowRight, CalendarClock, Sparkles } from 'lucide-react-native';
import { Chart, C, Header, Money, Screen, dateLabel, styles, money } from '../components/tally';
import { isBill } from '../services/bank';
import { changedPrice, loadGoal, predictSavings, predictionRequest, saveGoal, type Prediction, type PredictMode, type PredictScenario, type SavingsGoal } from '../services/predictions';
import { useAuth } from '../store/AuthProvider';
import { useBankTransactions } from '../store/useBankTransactions';
import { useTally } from '../store/TallyProvider';

const isoDate = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
/** Bills recur monthly on the day of their stored due date; this is the next such date from today (days are 1-28). */
const nextDue = (due: string, today: Date) => {
  const day = Number(due.slice(8, 10));
  const next = new Date(today.getFullYear(), today.getMonth() + (day >= today.getDate() ? 0 : 1), day);
  return isoDate(next);
};
const modes: PredictMode[] = ['Buy this', 'Different price', 'Skip it'];
const sameScenario = (a: PredictScenario, b: PredictScenario) =>
  a.mode === b.mode && a.cost === b.cost && a.frequency === b.frequency && a.years === b.years && (a.mode !== 'Different price' || a.change === b.change);

/** What the long-run number means for a scenario, in the same terms the backend compared. */
function describe(scenario: PredictScenario) {
  const times = `${scenario.frequency}× a month`;
  if (scenario.mode !== 'Different price') return `Skip ${money(scenario.cost)}, ${times}`;
  const newPrice = changedPrice(scenario);
  if (newPrice === scenario.cost) return `Same price, ${times}`;
  return newPrice < scenario.cost ? `Pay ${money(newPrice)} instead of ${money(scenario.cost)}, ${times}` : `Keep paying ${money(scenario.cost)} instead of ${money(newPrice)}, ${times}`;
}

function headline(scenario: PredictScenario) {
  const years = `IN ${scenario.years} ${scenario.years === 1 ? 'YEAR' : 'YEARS'}`;
  if (scenario.mode === 'Skip it') return `SKIP IT AND ${years} YOU COULD HAVE`;
  if (scenario.mode === 'Buy this') return `IF YOU SKIPPED IT INSTEAD, ${years}`;
  const newPrice = changedPrice(scenario);
  if (newPrice === scenario.cost) return `SAME PRICE, ${years}`;
  return newPrice < scenario.cost ? `PAYING THE LOWER PRICE, ${years}` : `AVOIDING THE PRICE RISE, ${years}`;
}

export default function Predict() {
  const { receipts } = useTally();
  const { user } = useAuth();
  const { rows: bank, canBank } = useBankTransactions();
  const [mode, setMode] = useState<PredictMode>('Buy this');
  const [cost, setCost] = useState(18);
  const [frequency, setFrequency] = useState(4);
  const [change, setChange] = useState(20);
  const [years, setYears] = useState(10);
  const [projection, setProjection] = useState<{ scenario: PredictScenario; result: Prediction } | null>(null);
  const [projecting, setProjecting] = useState(true);
  const [projectionError, setProjectionError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [goal, setGoal] = useState<SavingsGoal | null>(null);
  const [savingGoal, setSavingGoal] = useState(false);
  const scenario: PredictScenario = { mode, cost, frequency, change, years };

  // Sliders fire on every step, so wait until they settle; aborting drops replies for inputs that have since changed.
  useEffect(() => {
    const requested: PredictScenario = { mode, cost, frequency, change, years };
    const controller = new AbortController();
    setProjecting(true);
    setProjectionError(null);
    const timer = setTimeout(() => {
      predictSavings(predictionRequest(requested), controller.signal)
        .then((result) => { if (!controller.signal.aborted) setProjection({ scenario: requested, result }); })
        .catch((error) => { if (!controller.signal.aborted) setProjectionError(error instanceof Error ? error.message : 'The projection failed. Please try again.'); })
        .finally(() => { if (!controller.signal.aborted) setProjecting(false); });
    }, 500);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [mode, cost, frequency, change, years, attempt]);

  useEffect(() => {
    setGoal(null);
    if (!user) return;
    let active = true;
    loadGoal().then((saved) => { if (active) setGoal(saved); }).catch(() => {});
    return () => { active = false; };
  }, [user?.id]);

  const now = new Date();
  const thisMonth = isoDate(now).slice(0, 7);
  const bills = bank.filter(isBill).map((bill) => ({ ...bill, due: nextDue(bill.date, now) })).sort((a, b) => a.due.localeCompare(b.due));
  const monthlyBills = bills.reduce((sum, bill) => sum + bill.amount, 0);
  const billsDue = bills.filter((bill) => bill.due.startsWith(thisMonth)).reduce((sum, bill) => sum + bill.amount, 0);
  const base = receipts.slice(0, 4).reduce((sum, receipt) => sum + receipt.total, 0) * 1.9;
  const delta = mode === 'Skip it' ? -cost * frequency : mode === 'Different price' ? cost * frequency * change / 100 : cost * frequency;
  // Spread the scenario difference and the bills still due over the forecast horizon so every projected week responds smoothly.
  const progress = [0, .12, .27, .43, .6, .8, 1];
  const forecast = [base * .45, base * .57, base * .64, base * .7, base * .82, base * .9, base].map((value, index) => value + (delta + billsDue) * progress[index]);
  const comparison = [base * .45, base * .53, base * .62, base * .69, base * .76, base * .84, base].map((value, index) => value + billsDue * progress[index]);

  const current = projection && !projecting && !projectionError && sameScenario(projection.scenario, scenario) ? projection.result : null;
  const shown = projection?.result.recurring;
  const growth = shown ? Math.max(0, shown.future_savings - shown.total_saved) : 0;
  const goalMatches = Boolean(goal && sameScenario(goal, scenario));
  const canSave = goalMatches || Boolean(current && current.recurring.future_savings > 0);

  const toggleGoal = async () => {
    if (savingGoal || !canSave) return;
    const next: SavingsGoal | null = goalMatches || !current ? null : {
      ...scenario, futureSavings: current.recurring.future_savings, monthlySavings: current.recurring.monthly_savings, savedAt: new Date().toISOString(),
    };
    setSavingGoal(true);
    try {
      await saveGoal(next);
      setGoal(next);
    } catch (error) {
      Alert.alert('Could not update your goal', error instanceof Error ? error.message : 'Please try again.');
    } finally {
      setSavingGoal(false);
    }
  };

  return <Screen>
    <Header title="Predict" back="/" showBack={false} />
    <Text style={{ fontSize: 9, letterSpacing: 1.4, color: C.muted, fontWeight: '700', marginTop: 8 }}>A LITTLE WHAT-IF</Text>
    <Text style={{ fontFamily: 'Georgia', fontSize: 39, lineHeight: 42, color: C.navy, fontWeight: '600', marginTop: 7, marginBottom: 14 }}>Where could{`\n`}this month <Text style={{ fontStyle: 'italic', color: C.tomato }}>land?</Text></Text>
    <View style={{ borderWidth: 1, borderColor: C.rule, backgroundColor: '#F3EEE5', borderRadius: 20, padding: 15 }}>
      <Text style={{ fontSize: 9, letterSpacing: 1.3, color: C.muted, fontWeight: '700' }}>PROJECTED MONTH END</Text>
      <Money value={base + delta + billsDue} size={36} color={C.navy} />
      <Chart animate values={forecast} comparison={comparison} />
      <Text style={{ fontSize: 11, color: delta > 0 ? C.tomato : C.jungle, marginTop: 8, fontWeight: '700' }}>{delta > 0 ? '+' : '−'}{money(Math.abs(delta))} if you {mode.toLowerCase()}  ·  {(delta * .18).toFixed(1)} kg CO₂e</Text>
      {billsDue > 0 && <Text style={[styles.tiny, { marginTop: 4 }]}>Includes {money(billsDue)} of bills still due this month.</Text>}
    </View>
    <View style={{ flexDirection: 'row', backgroundColor: '#DED8CD', borderRadius: 13, padding: 4, marginVertical: 15 }}>
      {modes.map((item) => <Pressable key={item} onPress={() => setMode(item)} style={{ flex: 1, alignItems: 'center', justifyContent: 'center', minHeight: 38, borderRadius: 10, backgroundColor: mode === item ? '#FFFAF1' : 'transparent' }}><Text style={{ fontSize: 9, color: mode === item ? C.navy : '#6C716F', fontWeight: mode === item ? '700' : '400' }}>{item}</Text></Pressable>)}
    </View>
    <SliderRow label="Item cost" value={cost} min={1} max={80} format={money} set={setCost} />
    <SliderRow label="Times a month" value={frequency} min={1} max={12} format={(value) => `${value}×`} set={setFrequency} />
    {mode === 'Different price' && <SliderRow label="Price change" value={change} min={-50} max={60} format={(value) => `${value}%`} set={setChange} />}
    <SliderRow label="Years to grow" value={years} min={1} max={40} format={(value) => `${value} yr`} set={setYears} />
    <View style={{ borderWidth: 1, borderColor: C.rule, backgroundColor: '#E4ECE3', borderRadius: 20, padding: 15, marginTop: 12 }}>
      <View style={[styles.row, { gap: 7 }]}>
        <Text style={{ flex: 1, fontSize: 9, letterSpacing: 1.3, color: C.muted, fontWeight: '700' }}>{headline(scenario)}</Text>
        {projecting && <ActivityIndicator size="small" color={C.navy} />}
      </View>
      {shown ? <View style={{ opacity: current ? 1 : .45 }}>
        <Money value={shown.future_savings} size={36} color={C.jungle} />
        <Text style={[styles.tiny, { marginTop: 2 }]}>{money(shown.monthly_savings)} a month · {money(shown.total_saved)} set aside{growth > 0 ? ` + ${money(growth)} growth at ${Math.round(projection!.result.annual_return * 100)}% a year` : ''}</Text>
        <View style={[styles.row, { gap: 7, alignItems: 'flex-start', marginTop: 10 }]}>
          {projection!.result.explanation_source === 'gemini' && <Sparkles size={14} color={C.navy} style={{ marginTop: 2 }} />}
          <Text style={{ flex: 1, fontSize: 12, lineHeight: 17, color: C.ink, fontStyle: 'italic' }}>{projection!.result.explanation}</Text>
        </View>
      </View> : !projectionError && <Text style={[styles.tiny, { marginTop: 6 }]}>Working out your projection…</Text>}
      {projectionError && <View style={[styles.row, { gap: 8, marginTop: 8 }]}>
        <Text style={{ flex: 1, fontSize: 11, color: C.tomato }}>{projectionError}</Text>
        <Pressable onPress={() => setAttempt((value) => value + 1)} hitSlop={8}><Text style={{ fontSize: 11, color: C.navy, fontWeight: '700' }}>Try again</Text></Pressable>
      </View>}
    </View>
    {bills.length > 0 ? <View style={{ borderWidth: 1, borderColor: C.rule, backgroundColor: '#F3EEE5', borderRadius: 20, padding: 15, marginTop: 12, gap: 9 }}>
      <View style={[styles.row, { gap: 7 }]}><CalendarClock size={15} color={C.navy} /><Text style={{ flex: 1, fontSize: 9, letterSpacing: 1.3, color: C.muted, fontWeight: '700' }}>MONTHLY BILLS</Text><Text style={{ fontSize: 12, color: C.navy, fontWeight: '700' }}>{money(monthlyBills)}</Text></View>
      {bills.map((bill) => {
        const dueThisMonth = bill.due.startsWith(thisMonth);
        return <View key={bill.id} style={[styles.row, { gap: 8 }]}>
          <Text style={{ flex: 1, fontSize: 12, color: C.ink }} numberOfLines={1}>{bill.description}</Text>
          <Text style={[styles.tiny, { color: dueThisMonth ? C.tomato : C.muted }]}>due {dateLabel(bill.due)}</Text>
          <Text style={{ width: 70, textAlign: 'right', fontSize: 12, fontWeight: '600', color: C.ink }}>{money(bill.amount)}</Text>
        </View>;
      })}
      <Text style={styles.tiny}>{billsDue > 0 ? `${money(billsDue)} is still due before the month ends.` : 'Nothing else is due this month; the next bills land next month.'}</Text>
    </View> : canBank && <Pressable onPress={() => router.push('/profile')} style={[styles.row, { gap: 8, backgroundColor: '#DCE4E8', borderRadius: 16, padding: 13, marginTop: 12 }]}><CalendarClock size={16} color={C.navy} /><Text style={{ flex: 1, fontSize: 11, color: C.ink }}>Connect a demo bank in your profile to include your monthly bills.</Text><ArrowRight size={15} color={C.navy} /></Pressable>}
    {goal && !goalMatches && <View style={{ borderWidth: 1, borderColor: C.rule, borderRadius: 16, padding: 13, marginTop: 12 }}>
      <Text style={{ fontSize: 9, letterSpacing: 1.3, color: C.muted, fontWeight: '700' }}>YOUR GOAL</Text>
      <Text style={{ fontSize: 12, color: C.ink, marginTop: 4 }}>{describe(goal)} → {money(goal.futureSavings)} in {goal.years} {goal.years === 1 ? 'year' : 'years'}</Text>
    </View>}
    <Pressable disabled={!canSave || savingGoal} onPress={toggleGoal} style={{ height: 48, borderRadius: 15, backgroundColor: '#F2D76D', alignItems: 'center', justifyContent: 'center', marginTop: 12, opacity: !canSave || savingGoal ? .5 : 1 }}>
      <Text style={{ fontSize: 12, color: '#263342', fontWeight: '700' }}>{savingGoal ? 'Saving…' : goalMatches ? '✓ Saved as your goal · tap to remove' : goal ? 'Replace my goal with this' : 'Save as a goal'}</Text>
    </Pressable>
    <Text style={{ fontSize: 9, color: C.muted, textAlign: 'center', lineHeight: 14, marginHorizontal: 16, marginTop: 12 }}>Just a forecast to help you think it through. Growth assumes {Math.round((projection?.result.annual_return ?? .07) * 100)}% a year and isn't guaranteed.</Text>
  </Screen>;
}

function SliderRow({ label, value, min, max, format, set }: { label: string; value: number; min: number; max: number; format: (value: number) => string; set: (value: number) => void }) {
  return <View style={{ paddingVertical: 7 }}><View style={{ flexDirection: 'row', justifyContent: 'space-between' }}><Text style={{ fontSize: 11, color: C.ink }}>{label}</Text><Text style={{ fontSize: 11, color: C.navy, fontWeight: '700' }}>{format(value)}</Text></View><Slider minimumValue={min} maximumValue={max} step={1} value={value} onValueChange={(next) => set(Math.round(next))} minimumTrackTintColor={C.navy} maximumTrackTintColor="#C6C0B5" thumbTintColor={C.amber} /></View>;
}
