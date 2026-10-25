import React, { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { Chart, C, Header, Money, ReceiptRow, Screen, SectionTitle, styles, money } from '../components/tally';
import { isBankSpending } from '../services/bank';
import { useBankTransactions } from '../store/useBankTransactions';
import { useTally } from '../store/TallyProvider';

const WEEKS = 7;
const DAY_MS = 24 * 60 * 60 * 1000;
const localDay = (iso: string) => new Date(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10)));
const weekStart = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate() - d.getDay());

/** Chart slot (0 = six weeks ago … 6 = this week) for a YYYY-MM-DD date in Sunday-to-Saturday weeks, or -1 if outside the chart. */
function weekIndex(iso: string, today: Date) {
  if (!/^\d{4}-\d{2}-\d{2}/.test(iso)) return -1;
  const weeksAgo = Math.round((weekStart(today).getTime() - weekStart(localDay(iso)).getTime()) / (7 * DAY_MS));
  return weeksAgo >= 0 && weeksAgo < WEEKS ? WEEKS - 1 - weeksAgo : -1;
}

function weeklyTotals(entries: { date: string; amount: number }[], today: Date) {
  const totals = Array<number>(WEEKS).fill(0);
  for (const entry of entries) {
    const index = weekIndex(entry.date, today);
    if (index >= 0 && Number.isFinite(entry.amount)) totals[index] += entry.amount;
  }
  return totals.map((total) => Math.round(total * 100) / 100);
}

export default function Rewind() {
  const { receipts } = useTally();
  const { rows: bank } = useBankTransactions();
  const [selected, setSelected] = useState<(typeof receipts)[number] | null>(null);
  const [removed, setRemoved] = useState(false);
  const today = new Date();
  const receiptWeeks = weeklyTotals(receipts.map((receipt) => ({ date: receipt.date, amount: receipt.total })), today);
  const bankWeeks = weeklyTotals(bank.filter(isBankSpending).map((txn) => ({ date: txn.date, amount: txn.amount })), today);
  const values = receiptWeeks.map((total, index) => Math.round((total + bankWeeks[index]) * 100) / 100);
  const receiptSum = receiptWeeks.reduce((sum, total) => sum + total, 0);
  const bankSum = bankWeeks.reduce((sum, total) => sum + total, 0);
  const selectedWeek = selected ? weekIndex(selected.date, today) : -1;
  const after = removed && selectedWeek >= 0 ? values.map((value, index) => index === selectedWeek ? Math.max(0, value - selected!.total) : value) : values;
  const pick = (receipt: (typeof receipts)[number]) => { setSelected(receipt); setRemoved(false); };

  return <Screen>
    <Header title="Rewind" back="/" />
    <Text style={styles.eyebrow}>THE WHAT-IF MACHINE</Text>
    <Text style={styles.h1}>One less{`\n`}<Text style={{ color: C.tomato, fontStyle: 'italic' }}>thing.</Text></Text>
    <Text style={[styles.body, { marginBottom: 16 }]}>What if you left it on the shelf?</Text>
    <View style={styles.panel}>
      <Text style={styles.eyebrow}>YOUR WEEKLY SPENDING{removed && selectedWeek >= 0 ? ' · BEFORE / AFTER' : ''}</Text>
      <Chart animate values={after} comparison={removed && selectedWeek >= 0 ? values : undefined} />
      <Text style={[styles.tiny, { marginTop: 6 }]}>
        {receiptSum + bankSum === 0 ? 'No spending in the last 7 weeks yet. Scan a receipt or connect a demo bank to fill this in.'
          : `Last 7 weeks: ${money(receiptSum)} from receipts${bankSum > 0 ? ` + ${money(bankSum)} from your bank` : ''}.`}
      </Text>
    </View>
    <SectionTitle>Pick a purchase</SectionTitle>
    {receipts.slice(0, 8).map((receipt) => <ReceiptRow key={receipt.id} merchant={receipt.merchant} date={receipt.date} total={receipt.total} onPress={() => pick(receipt)} />)}
    {selected && <View style={{ backgroundColor: '#F2EEE4', borderRadius: 18, padding: 14, marginTop: 14 }}>
      <Text style={styles.eyebrow}>IF YOU SKIPPED {selected.merchant.toUpperCase()}</Text>
      <Money value={selected.total} size={30} color={removed ? C.jungle : C.tomato} />
      <Text style={[styles.tiny, { marginTop: 4, marginBottom: 12 }]}>{selected.items.reduce((sum, item) => sum + item.carbon, 0).toFixed(1)} kg CO₂e off the books</Text>
      <Pressable onPress={() => setRemoved(!removed)} style={{ backgroundColor: C.navy, borderRadius: 14, minHeight: 46, alignItems: 'center', justifyContent: 'center' }}><Text style={{ color: 'white', fontWeight: '700', fontSize: 12 }}>{removed ? 'Reset' : 'Remove this purchase'}</Text></Pressable>
      <Text style={[styles.tiny, { textAlign: 'center', marginTop: 9 }]}>{selectedWeek < 0 ? 'This purchase is older than the 7 weeks on the chart. ' : ''}Just a what-if. Your receipt is still right where it was.</Text>
    </View>}
  </Screen>;
}
