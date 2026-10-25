import React, { useMemo, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { router } from 'expo-router';
import { ArrowRight, CalendarClock, Landmark, PiggyBank, Sparkles } from 'lucide-react-native';
import { Chart, C, CategoryIcon, Empty, Eyebrow, Header, Money, Screen, SectionTitle, dateLabel, money, styles } from '../components/tally';
import { categories } from '../data/mock';
import { isBankIncome, isBankSpending, isBill, savingsTotal } from '../services/bank';
import { categoryFromDb } from '../services/shopping';
import { useBankTransactions } from '../store/useBankTransactions';
import { useTally } from '../store/TallyProvider';

const barColors = [C.navy, '#D97751', '#8F9C76', '#6D8DA0', C.amber, '#9B8A7D'];

export default function Dashboard() {
  const { receipts } = useTally();
  const { rows: allBank, error: bankError, canBank } = useBankTransactions();
  const [period, setPeriod] = useState('This month');
  const bills = allBank.filter(isBill);
  const bank = allBank.filter((txn) => !isBill(txn));
  const saved = savingsTotal(bank);
  const monthlyBills = bills.reduce((sum, bill) => sum + bill.amount, 0);

  const data = useMemo(() => categories.map((category) => ({
    category,
    total: receipts.flatMap((receipt) => receipt.items).filter((item) => item.category === category).reduce((sum, item) => sum + item.price * item.quantity, 0),
  })), [receipts]);
  const grand = data.reduce((sum, item) => sum + item.total, 0);
  const carbon = receipts.flatMap((receipt) => receipt.items).reduce((sum, item) => sum + item.carbon, 0);
  const chartValues = receipts.slice(0, 7).reverse().map((receipt) => receipt.total);

  const bankSpent = bank.filter(isBankSpending).reduce((sum, txn) => sum + txn.amount, 0);
  const bankIn = bank.filter(isBankIncome).reduce((sum, txn) => sum + txn.amount, 0);
  const bankByCategory = useMemo(() => categories.map((category) => ({
    category,
    total: bank.filter((txn) => isBankSpending(txn) && categoryFromDb(txn.category) === category).reduce((sum, txn) => sum + txn.amount, 0),
  })).filter((item) => item.total > 0).sort((a, b) => b.total - a.total), [bank]);
  // CATch's own transfers out of checking mirror the savings deposits, so only the savings side is listed.
  const recent = bank.filter((txn) => txn.type !== 'transfer').slice(0, 5);

  if (!receipts.length && !bank.length) return <Screen>
    <Header title="Dashboard" back="/" />
    <Eyebrow>THE FULL PICTURE</Eyebrow>
    <Text style={styles.h1}>Dashboard</Text>
    <Empty title="Nothing to total yet" copy="Your spending, savings, and impact will appear after you scan your first receipt or connect a demo bank in your profile." action={() => router.push('/scan')} />
  </Screen>;

  return <Screen>
    <Header title="Dashboard" back="/" />
    <Eyebrow>THE FULL PICTURE</Eyebrow>
    <Text style={styles.h1}>Dashboard</Text>
    <Text style={[styles.body, { marginBottom: 16 }]}>Good habits, in plain numbers.</Text>
    {receipts.length > 0 && <View style={{ flexDirection: 'row', backgroundColor: '#DED8CD', padding: 3, borderRadius: 11, marginBottom: 15 }}>
      {['This week', 'This month', 'All time'].map((item) => <Pressable key={item} onPress={() => setPeriod(item)} style={{ flex: 1, alignItems: 'center', padding: 9, borderRadius: 8, backgroundColor: period === item ? '#FFFAF1' : 'transparent' }}><Text style={{ fontSize: 10, color: period === item ? C.navy : '#6C716F' }}>{item}</Text></Pressable>)}
    </View>}
    {receipts.length > 0 && <View style={styles.panel}>
      <View style={[styles.row, { justifyContent: 'space-between' }]}><View><Eyebrow>SPENT · FROM RECEIPTS</Eyebrow><Money value={grand} size={32} /></View></View>
      <Chart values={chartValues.length > 1 ? chartValues : [0, chartValues[0]]} />
    </View>}
    {receipts.length > 0 && <SectionTitle right={<Text style={styles.tiny}>{receipts.length} receipts</Text>}>Where it goes</SectionTitle>}
    {receipts.length > 0 && <View style={{ height: 10, borderRadius: 9, overflow: 'hidden', flexDirection: 'row', marginBottom: 8 }}>
      {data.filter((item) => item.total > 0).map((item, index) => <View key={item.category} style={{ width: `${item.total / grand * 100}%`, backgroundColor: barColors[index] }} />)}
    </View>}
    {receipts.length > 0 && data.filter((item) => item.total > 0).map((item, index) => <View key={item.category} style={[styles.row, styles.divider, { minHeight: 52, gap: 10 }]}><CategoryIcon category={item.category} /><View style={{ flex: 1 }}><View style={[styles.row, { justifyContent: 'space-between', marginBottom: 5 }]}><Text style={{ fontSize: 12, fontWeight: '700', color: C.ink }}>{item.category}</Text><Text style={styles.tiny}>{Math.round(item.total / grand * 100)}%</Text></View><View style={{ height: 3, backgroundColor: '#DDD7CC', borderRadius: 4 }}><View style={{ height: 3, borderRadius: 4, width: `${item.total / grand * 100}%`, backgroundColor: barColors[index] }} /></View></View><Money value={item.total} size={12} /></View>)}
    {receipts.length > 0 && <View style={{ flexDirection: 'row', gap: 10, marginTop: 16 }}>
      <View style={{ flex: 1, backgroundColor: '#E2E6E3', borderRadius: 17, padding: 13 }}><Eyebrow>CARBON TOTAL</Eyebrow><Text style={{ fontFamily: 'Georgia', fontSize: 28, color: C.navy }}>{carbon.toFixed(1)}<Text style={{ fontSize: 14 }}> kg</Text></Text><Text style={styles.tiny}>CO₂ equivalent</Text></View>
      <View style={{ flex: 1, backgroundColor: '#D8EAD8', borderRadius: 17, padding: 13 }}><Eyebrow>SAVINGS FOUND</Eyebrow><Text style={{ fontFamily: 'Georgia', fontSize: 28, color: '#157536' }}>{money(saved)}</Text><Text style={styles.tiny}>{saved > 0 ? 'Moved to CATch savings' : 'No accepted swaps yet'}</Text></View>
    </View>}
    {!receipts.length && <Pressable onPress={() => router.push('/scan')} style={[styles.panel, styles.row, { gap: 8 }]}><Text style={{ flex: 1, fontSize: 12, color: C.ink }}>Scan a receipt to see categories and carbon for what you buy.</Text><ArrowRight size={15} color={C.navy} /></Pressable>}

    {bank.length > 0 && <SectionTitle right={<Text style={styles.tiny}>{bank.filter((txn) => txn.type !== 'transfer').length} transactions</Text>}>Bank</SectionTitle>}
    {bank.length > 0 && <View style={{ flexDirection: 'row', gap: 10 }}>
      <View style={{ flex: 1, backgroundColor: '#F3E1DB', borderRadius: 17, padding: 13 }}><Eyebrow>SPENT · BANK</Eyebrow><Text style={{ fontFamily: 'Georgia', fontSize: 24, color: C.navy }}>{money(bankSpent)}</Text><Text style={styles.tiny}>{bank.filter(isBankSpending).length} purchases</Text></View>
      <View style={{ flex: 1, backgroundColor: '#D8EAD8', borderRadius: 17, padding: 13 }}><Eyebrow>MONEY IN</Eyebrow><Text style={{ fontFamily: 'Georgia', fontSize: 24, color: '#157536' }}>{money(bankIn)}</Text><Text style={styles.tiny}>Paychecks and deposits</Text></View>
    </View>}
    {bank.length > 0 && <View style={[styles.row, { gap: 10, backgroundColor: '#E3EFE0', borderRadius: 16, padding: 13, marginTop: 10 }]}>
      <PiggyBank size={20} color="#157536" />
      <View style={{ flex: 1 }}><Eyebrow>IN CATCH SAVINGS</Eyebrow><Text style={styles.tiny}>{saved > 0 ? 'Moved here when you apply swaps.' : 'Apply a swap on Compare to start saving.'}</Text></View>
      <Text style={{ fontFamily: 'Georgia', fontSize: 22, color: '#157536' }}>{money(saved)}</Text>
    </View>}
    {bankByCategory.map((item, index) => <View key={item.category} style={[styles.row, styles.divider, { minHeight: 50, gap: 10 }]}>
      <CategoryIcon category={item.category} />
      <View style={{ flex: 1 }}><View style={[styles.row, { justifyContent: 'space-between', marginBottom: 5 }]}><Text style={{ fontSize: 12, fontWeight: '700', color: C.ink }}>{item.category}</Text><Text style={styles.tiny}>{Math.round(item.total / bankSpent * 100)}%</Text></View><View style={{ height: 3, backgroundColor: '#DDD7CC', borderRadius: 4 }}><View style={{ height: 3, borderRadius: 4, width: `${item.total / bankSpent * 100}%`, backgroundColor: barColors[index % barColors.length] }} /></View></View>
      <Money value={item.total} size={12} />
    </View>)}
    {bills.length > 0 && <Pressable onPress={() => router.push('/predict')} style={[styles.row, { gap: 10, backgroundColor: '#DCE4E8', borderRadius: 16, padding: 13, marginTop: 14 }]}>
      <CalendarClock size={18} color={C.navy} />
      <Text style={{ flex: 1, fontSize: 11, color: C.ink }}><Text style={{ fontWeight: '700' }}>{bills.length} monthly bills · {money(monthlyBills)}{`\n`}</Text>See how they shape your month in Predict.</Text>
      <ArrowRight size={15} color={C.navy} />
    </Pressable>}
    {bank.length > 0 && <View style={[styles.panel, { marginTop: 14, gap: 9 }]}>
      <Eyebrow>RECENT BANK ACTIVITY</Eyebrow>
      {recent.map((txn) => {
        const incoming = isBankIncome(txn);
        const toSavings = txn.type === 'savings';
        return <View key={txn.id} style={[styles.row, { gap: 8 }]}>
          <Text style={[styles.tiny, { width: 46 }]}>{dateLabel(txn.date)}</Text>
          <Text style={{ flex: 1, fontSize: 12, color: C.ink }} numberOfLines={1}>{toSavings ? 'Moved to savings' : txn.description}</Text>
          <Text style={{ fontSize: 12, fontWeight: '600', color: incoming || toSavings ? '#157536' : C.ink }}>{incoming ? '+' : toSavings ? '→ ' : isBankSpending(txn) ? '−' : ''}{money(txn.amount)}</Text>
        </View>;
      })}
      <Text style={styles.tiny}>Bank and receipt totals are kept separate, so a purchase you also scanned is never counted twice.</Text>
    </View>}
    {!bank.length && canBank && <Pressable onPress={() => router.push('/profile')} style={[styles.row, { gap: 8, backgroundColor: '#DCE4E8', borderRadius: 16, padding: 13, marginTop: 16 }]}><Landmark size={16} color={C.navy} /><Text style={{ flex: 1, fontSize: 11, color: C.ink }}>Connect a demo bank in your profile to see purchases and paychecks here.</Text><ArrowRight size={15} color={C.navy} /></Pressable>}
    {!!bankError && <Text style={[styles.tiny, { color: C.tomato, marginTop: 8 }]}>{bankError}</Text>}

    <View style={[styles.row, { gap: 9, backgroundColor: '#F3D969', borderRadius: 16, padding: 13, marginTop: 16 }]}><Sparkles size={18} color="#795B12" /><Text style={{ fontSize: 11, lineHeight: 17, color: C.ink, flex: 1 }}><Text style={{ fontWeight: '700' }}>Your picture gets clearer{`\n`}</Text>Keep scanning to spot spending and carbon patterns.</Text></View>
    <Pressable onPress={() => router.push('/shopping')} style={[styles.row, { justifyContent: 'center', gap: 6, padding: 14 }]}><Text style={{ fontSize: 11, color: C.navy, fontWeight: '700' }}>Open your shopping list</Text><ArrowRight size={15} color={C.navy} /></Pressable>
  </Screen>;
}
