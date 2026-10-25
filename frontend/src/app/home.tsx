import React, { useEffect, useRef, useState } from 'react';
import { Image, Pressable, Text, View } from 'react-native';
import { router } from 'expo-router';
import { ArrowRight, ChevronRight, RotateCcw, ShoppingBasket, Sparkles, TrendingDown, UserRound } from 'lucide-react-native';
import { Chart, C, Eyebrow, MorphPressable, ReceiptRow, money, Screen, SectionTitle, styles } from '../components/tally';
import { useTally } from '../store/TallyProvider';
import { useTransitions } from '../store/TransitionProvider';
import { useLocalSearchParams } from 'expo-router';

export default function Home() {
  const { receipts, shopping } = useTally();
  const [period, setPeriod] = useState('Week');
  const [graphReady, setGraphReady] = useState(false);
  const { intro } = useLocalSearchParams<{ intro?: string }>();
  const introPending = useRef(intro === '1');
  const transitions = useTransitions();
  const recent = [...receipts].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 5);
  const total = recent.slice(0, 4).reduce((sum, receipt) => sum + receipt.total, 0);
  const values = [232, 268, 249, 310, 284, 347, Math.max(total, 160)];
  const entranceDelay = intro === '1' ? 650 : 0;
  useEffect(() => {
    const timer = setTimeout(() => {
      setGraphReady(true);
      introPending.current = false;
    }, introPending.current ? 650 : 80);
    return () => clearTimeout(timer);
  }, []);

  return (
    <Screen popDelay={entranceDelay}>
      <View>
        <View style={[styles.row, { gap: 6, marginBottom: 20 }]}>
          <Image source={require('../../assets/catch-logo.png')} resizeMode="contain" style={{ height: 24, width: 27 }} />
          <Text style={{ fontSize: 18, fontWeight: '700', color: C.navy }}>CATch</Text>
          <Pressable accessibilityRole="button" accessibilityLabel="Open profile" onPress={() => transitions.goTo('/profile','profile')} style={{ marginLeft: 'auto', height: 40, width: 40, borderRadius: 14, borderWidth: 1, borderColor: C.rule, backgroundColor: '#F3EEE5', alignItems: 'center', justifyContent: 'center' }}><UserRound size={19} color={C.navy} /></Pressable>
        </View>
        <Eyebrow>SATURDAY, OCTOBER 24</Eyebrow>
        <Text style={[styles.h1, { fontSize: 41 }]}>Good morning,{`\n`}<Text style={{ color: C.tomato, fontStyle: 'italic' }}>Alex.</Text></Text>
      </View>

      <Pressable onPress={() => transitions.goTo('/calendar','calendar')} style={{ flexDirection: 'row', alignItems: 'center', gap: 7, backgroundColor: '#F5CE58', borderRadius: 13, padding: 10, marginTop: 14, marginBottom: 24 }}>
        <Sparkles size={15} color="#7C5610" />
        <Text style={{ fontSize: 12, fontWeight: '700', color: C.ink }}>5 day scan streak</Text>
        <Text style={{ fontSize: 10, color: '#694F10', marginLeft: 'auto' }}>Keep it going</Text>
      </Pressable>

      <View>
        <View style={[styles.row, { justifyContent: 'space-between', alignItems: 'flex-start' }]}>
          <View>
            <Eyebrow>YOUR SPENDING</Eyebrow>
            <Text style={{ fontFamily: 'Georgia', fontSize: 36, color: C.ink }}>{money(total)}</Text>
            <View style={[styles.row, { gap: 4, marginTop: 5 }]}>
              <TrendingDown size={15} color={C.jungle} />
              <Text style={{ fontSize: 11, color: C.jungle }}>$38 less than last week</Text>
            </View>
          </View>
          <View style={{ flexDirection: 'row', backgroundColor: '#DED8CD', padding: 3, borderRadius: 11 }}>
            {['Week', 'Month', 'Total'].map((item) => (
              <Pressable key={item} onPress={() => setPeriod(item)} style={{ paddingVertical: 6, paddingHorizontal: 8, borderRadius: 8, backgroundColor: period === item ? '#FFFAF1' : 'transparent' }}>
                <Text style={{ fontSize: 9, color: period === item ? C.navy : '#6C716F', fontWeight: period === item ? '700' : '400' }}>{item}</Text>
              </Pressable>
            ))}
          </View>
        </View>
        <View style={{ marginTop: 5 }}>
          <Chart animate={graphReady} values={period === 'Week' ? values : period === 'Month' ? values.map((value) => value * 3.8) : values.map((value) => value * 8.2)} />
        </View>
      </View>

      <SectionTitle right={<Pressable onPress={() => router.push('/dashboard')} style={[styles.row, { gap: 3 }]}><Text style={{ fontSize: 11, color: C.navy, fontWeight: '700' }}>See all</Text><ArrowRight size={14} color={C.navy} /></Pressable>}>Recent receipts</SectionTitle>
      {recent.slice(0, 4).map((receipt) => <ReceiptRow key={receipt.id} merchant={receipt.merchant} date={receipt.date} total={receipt.total} carbon={receipt.items.reduce((sum, item) => sum + item.carbon, 0)} onPress={() => router.push({ pathname: '/receipt/[id]', params: { id: receipt.id } })} morphTo={{ pathname: '/receipt/[id]', params: { id: receipt.id } }} />)}

      <SectionTitle>Little shortcuts</SectionTitle>
      <MorphPressable route="/shopping" style={[styles.row, { paddingVertical: 12, gap: 9, borderBottomWidth: 1, borderColor: C.rule }]}>
        <View style={{ width: 36, height: 36, borderRadius: 12, backgroundColor: '#F8D96C', alignItems: 'center', justifyContent: 'center' }}><ShoppingBasket size={18} color="#72560C" /></View>
        <View style={{ flex: 1 }}><Text style={{ fontSize: 12, fontWeight: '700', color: C.ink }}>Shopping list</Text><Text style={styles.tiny}>{shopping.length} items to pick up</Text></View>
        <ChevronRight size={16} color="#818982" />
      </MorphPressable>
      <MorphPressable route="/rewind" style={[styles.row, { paddingVertical: 12, gap: 9, borderBottomWidth: 1, borderColor: C.rule }]}>
        <View style={{ width: 36, height: 36, borderRadius: 12, backgroundColor: '#D3DCE4', alignItems: 'center', justifyContent: 'center' }}><RotateCcw size={18} color={C.navy} /></View>
        <View style={{ flex: 1 }}><Text style={{ fontSize: 12, fontWeight: '700', color: C.ink }}>Rewind a purchase</Text><Text style={styles.tiny}>Try a different what-if</Text></View>
        <ChevronRight size={16} color="#818982" />
      </MorphPressable>
      <Text style={[styles.tiny, { textAlign: 'center', marginTop: 22 }]}>Small choices add up. You’ve got this.</Text>
    </Screen>
  );
}


