import React, { useState } from 'react';
import { Alert, Pressable, Text, View } from 'react-native';
import { router } from 'expo-router';
import Slider from '@react-native-community/slider';
import { ArrowRight, CalendarClock } from 'lucide-react-native';
import { Chart, C, Header, Money, Screen, dateLabel, styles, money } from '../components/tally';
import { isBill } from '../services/bank';
import { useBankTransactions } from '../store/useBankTransactions';
import { useTally } from '../store/TallyProvider';

const isoDate = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
/** Bills recur monthly on the day of their stored due date; this is the next such date from today (days are 1-28). */
const nextDue = (due: string, today: Date) => {
  const day = Number(due.slice(8, 10));
  const next = new Date(today.getFullYear(), today.getMonth() + (day >= today.getDate() ? 0 : 1), day);
  return isoDate(next);
};

export default function Predict() {
  const { receipts } = useTally();
  const { rows: bank, canBank } = useBankTransactions();
  const [mode, setMode] = useState('Buy this');
  const [cost, setCost] = useState(18);
  const [frequency, setFrequency] = useState(4);
  const [change, setChange] = useState(20);
  const [goal, setGoal] = useState(false);
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
      {['Buy this', 'Different price', 'Skip it'].map((item) => <Pressable key={item} onPress={() => setMode(item)} style={{ flex: 1, alignItems: 'center', justifyContent: 'center', minHeight: 38, borderRadius: 10, backgroundColor: mode === item ? '#FFFAF1' : 'transparent' }}><Text style={{ fontSize: 9, color: mode === item ? C.navy : '#6C716F', fontWeight: mode === item ? '700' : '400' }}>{item}</Text></Pressable>)}
    </View>
    <SliderRow label="Item cost" value={cost} min={1} max={80} format={money} set={setCost} />
    <SliderRow label="Times this month" value={frequency} min={1} max={12} format={(value) => `${value}×`} set={setFrequency} />
    {mode === 'Different price' && <SliderRow label="Price change" value={change} min={-50} max={60} format={(value) => `${value}%`} set={setChange} />}
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
    <Pressable onPress={() => { setGoal(!goal); Alert.alert(goal ? 'Goal removed' : 'Goal saved', 'Your goal is saved on this device.'); }} style={{ height: 48, borderRadius: 15, backgroundColor: '#F2D76D', alignItems: 'center', justifyContent: 'center', marginTop: 12 }}><Text style={{ fontSize: 12, color: '#263342', fontWeight: '700' }}>{goal ? '✓ Goal saved for this month' : 'Save as a goal'}</Text></Pressable>
    <Text style={{ fontSize: 9, color: C.muted, textAlign: 'center', lineHeight: 14, marginHorizontal: 16, marginTop: 12 }}>Just a forecast to help you think it through. Nothing changes unless you say so.</Text>
  </Screen>;
}

function SliderRow({ label, value, min, max, format, set }: { label: string; value: number; min: number; max: number; format: (value: number) => string; set: (value: number) => void }) {
  return <View style={{ paddingVertical: 7 }}><View style={{ flexDirection: 'row', justifyContent: 'space-between' }}><Text style={{ fontSize: 11, color: C.ink }}>{label}</Text><Text style={{ fontSize: 11, color: C.navy, fontWeight: '700' }}>{format(value)}</Text></View><Slider minimumValue={min} maximumValue={max} step={1} value={value} onValueChange={set} minimumTrackTintColor={C.navy} maximumTrackTintColor="#C6C0B5" thumbTintColor={C.amber} /></View>;
}

