import React, { useMemo, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { router } from 'expo-router';
import { ArrowRight, Sparkles } from 'lucide-react-native';
import { Chart, C, CategoryIcon, Empty, Eyebrow, Header, Money, Screen, SectionTitle, styles } from '../components/tally';
import { categories } from '../data/mock';
import { useTally } from '../store/TallyProvider';

export default function Dashboard() {
  const { receipts } = useTally();
  const [period, setPeriod] = useState('This month');
  const data = useMemo(() => categories.map((category) => ({
    category,
    total: receipts.flatMap((receipt) => receipt.items).filter((item) => item.category === category).reduce((sum, item) => sum + item.price * item.quantity, 0),
  })), [receipts]);
  const grand = data.reduce((sum, item) => sum + item.total, 0);
  const carbon = receipts.flatMap((receipt) => receipt.items).reduce((sum, item) => sum + item.carbon, 0);
  const chartValues = receipts.slice(0, 7).reverse().map((receipt) => receipt.total);

  if (!receipts.length) return <Screen>
    <Header title="Dashboard" back="/" />
    <Eyebrow>THE FULL PICTURE</Eyebrow>
    <Text style={styles.h1}>Dashboard</Text>
    <Empty title="Nothing to total yet" copy="Your spending, savings, and impact will appear after you scan your first receipt." action={() => router.push('/scan')} />
  </Screen>;

  return <Screen>
    <Header title="Dashboard" back="/" />
    <Eyebrow>THE FULL PICTURE</Eyebrow>
    <Text style={styles.h1}>Dashboard</Text>
    <Text style={[styles.body, { marginBottom: 16 }]}>Good habits, in plain numbers.</Text>
    <View style={{ flexDirection: 'row', backgroundColor: '#DED8CD', padding: 3, borderRadius: 11, marginBottom: 15 }}>
      {['This week', 'This month', 'All time'].map((item) => <Pressable key={item} onPress={() => setPeriod(item)} style={{ flex: 1, alignItems: 'center', padding: 9, borderRadius: 8, backgroundColor: period === item ? '#FFFAF1' : 'transparent' }}><Text style={{ fontSize: 10, color: period === item ? C.navy : '#6C716F' }}>{item}</Text></Pressable>)}
    </View>
    <View style={styles.panel}>
      <View style={[styles.row, { justifyContent: 'space-between' }]}><View><Eyebrow>TOTAL SPENT</Eyebrow><Money value={grand} size={32} /></View></View>
      <Chart values={chartValues.length > 1 ? chartValues : [0, chartValues[0]]} />
    </View>
    <SectionTitle right={<Text style={styles.tiny}>{receipts.length} receipts</Text>}>Where it goes</SectionTitle>
    <View style={{ height: 10, borderRadius: 9, overflow: 'hidden', flexDirection: 'row', marginBottom: 8 }}>
      {data.filter((item) => item.total > 0).map((item, index) => <View key={item.category} style={{ width: `${item.total / grand * 100}%`, backgroundColor: [C.navy, '#D97751', '#8F9C76', '#6D8DA0', C.amber, '#9B8A7D'][index] }} />)}
    </View>
    {data.filter((item) => item.total > 0).map((item, index) => <View key={item.category} style={[styles.row, styles.divider, { minHeight: 52, gap: 10 }]}><CategoryIcon category={item.category} /><View style={{ flex: 1 }}><View style={[styles.row, { justifyContent: 'space-between', marginBottom: 5 }]}><Text style={{ fontSize: 12, fontWeight: '700', color: C.ink }}>{item.category}</Text><Text style={styles.tiny}>{Math.round(item.total / grand * 100)}%</Text></View><View style={{ height: 3, backgroundColor: '#DDD7CC', borderRadius: 4 }}><View style={{ height: 3, borderRadius: 4, width: `${item.total / grand * 100}%`, backgroundColor: [C.navy, '#D97751', '#8F9C76', '#6D8DA0', C.amber, '#9B8A7D'][index] }} /></View></View><Money value={item.total} size={12} /></View>)}
    <View style={{ flexDirection: 'row', gap: 10, marginTop: 16 }}>
      <View style={{ flex: 1, backgroundColor: '#E2E6E3', borderRadius: 17, padding: 13 }}><Eyebrow>CARBON TOTAL</Eyebrow><Text style={{ fontFamily: 'Georgia', fontSize: 28, color: C.navy }}>{carbon.toFixed(1)}<Text style={{ fontSize: 14 }}> kg</Text></Text><Text style={styles.tiny}>CO₂ equivalent</Text></View>
      <View style={{ flex: 1, backgroundColor: '#D8EAD8', borderRadius: 17, padding: 13 }}><Eyebrow>SAVINGS FOUND</Eyebrow><Text style={{ fontFamily: 'Georgia', fontSize: 28, color: '#157536' }}>$0.00</Text><Text style={styles.tiny}>No accepted swaps yet</Text></View>
    </View>
    <View style={[styles.row, { gap: 9, backgroundColor: '#F3D969', borderRadius: 16, padding: 13, marginTop: 16 }]}><Sparkles size={18} color="#795B12" /><Text style={{ fontSize: 11, lineHeight: 17, color: C.ink, flex: 1 }}><Text style={{ fontWeight: '700' }}>Your picture gets clearer{`\n`}</Text>Keep scanning to spot spending and carbon patterns.</Text></View>
    <Pressable onPress={() => router.push('/shopping')} style={[styles.row, { justifyContent: 'center', gap: 6, padding: 14 }]}><Text style={{ fontSize: 11, color: C.navy, fontWeight: '700' }}>Open your shopping list</Text><ArrowRight size={15} color={C.navy} /></Pressable>
  </Screen>;
}
