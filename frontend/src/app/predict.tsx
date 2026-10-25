import React, { useState } from 'react';
import { Alert, Pressable, Text, View } from 'react-native';
import Slider from '@react-native-community/slider';
import { Chart, C, Header, Money, Screen, styles, money } from '../components/tally';
import { useTally } from '../store/TallyProvider';

export default function Predict() {
  const { receipts } = useTally();
  const [mode, setMode] = useState('Buy this');
  const [cost, setCost] = useState(18);
  const [frequency, setFrequency] = useState(4);
  const [change, setChange] = useState(20);
  const [goal, setGoal] = useState(false);
  const base = receipts.slice(0, 4).reduce((sum, receipt) => sum + receipt.total, 0) * 1.9;
  const delta = mode === 'Skip it' ? -cost * frequency : mode === 'Different price' ? cost * frequency * change / 100 : cost * frequency;

  return <Screen>
    <Header title="Predict" back="/" />
    <Text style={{ fontSize: 9, letterSpacing: 1.4, color: C.muted, fontWeight: '700', marginTop: 8 }}>A LITTLE WHAT-IF</Text>
    <Text style={{ fontFamily: 'Georgia', fontSize: 39, lineHeight: 42, color: C.navy, marginTop: 7, marginBottom: 14 }}>Where could{`\n`}this month <Text style={{ fontStyle: 'italic', color: C.tomato }}>land?</Text></Text>
    <View style={{ borderWidth: 1, borderColor: C.rule, backgroundColor: '#F3EEE5', borderRadius: 20, padding: 15 }}>
      <Text style={{ fontSize: 9, letterSpacing: 1.3, color: C.muted, fontWeight: '700' }}>PROJECTED MONTH END</Text>
      <Money value={base + delta} size={36} color={C.navy} />
      <Chart values={[base * .45, base * .57, base * .64, base * .7, base * .82, base * .9, base + delta]} comparison={[base * .45, base * .53, base * .62, base * .69, base * .76, base * .84, base]} />
      <Text style={{ fontSize: 11, color: delta > 0 ? C.tomato : C.jungle, marginTop: 8, fontWeight: '700' }}>{delta > 0 ? '+' : '−'}{money(Math.abs(delta))} if you {mode.toLowerCase()}  ·  {(delta * .18).toFixed(1)} kg CO₂e</Text>
    </View>
    <View style={{ flexDirection: 'row', backgroundColor: '#DED8CD', borderRadius: 13, padding: 4, marginVertical: 15 }}>
      {['Buy this', 'Different price', 'Skip it'].map((item) => <Pressable key={item} onPress={() => setMode(item)} style={{ flex: 1, alignItems: 'center', justifyContent: 'center', minHeight: 38, borderRadius: 10, backgroundColor: mode === item ? '#FFFAF1' : 'transparent' }}><Text style={{ fontSize: 9, color: mode === item ? C.navy : '#6C716F', fontWeight: mode === item ? '700' : '400' }}>{item}</Text></Pressable>)}
    </View>
    <SliderRow label="Item cost" value={cost} min={1} max={80} format={money} set={setCost} />
    <SliderRow label="Times this month" value={frequency} min={1} max={12} format={(value) => `${value}×`} set={setFrequency} />
    {mode === 'Different price' && <SliderRow label="Price change" value={change} min={-50} max={60} format={(value) => `${value}%`} set={setChange} />}
    <Pressable onPress={() => { setGoal(!goal); Alert.alert(goal ? 'Goal removed' : 'Goal saved', 'Your goal is saved on this device.'); }} style={{ height: 48, borderRadius: 15, backgroundColor: '#F2D76D', alignItems: 'center', justifyContent: 'center', marginTop: 12 }}><Text style={{ fontSize: 12, color: '#263342', fontWeight: '700' }}>{goal ? '✓ Goal saved for this month' : 'Save as a goal'}</Text></Pressable>
    <Text style={{ fontSize: 9, color: C.muted, textAlign: 'center', lineHeight: 14, marginHorizontal: 16, marginTop: 12 }}>Just a forecast to help you think it through. Nothing changes unless you say so.</Text>
  </Screen>;
}

function SliderRow({ label, value, min, max, format, set }: { label: string; value: number; min: number; max: number; format: (value: number) => string; set: (value: number) => void }) {
  return <View style={{ paddingVertical: 7 }}><View style={{ flexDirection: 'row', justifyContent: 'space-between' }}><Text style={{ fontSize: 11, color: C.ink }}>{label}</Text><Text style={{ fontSize: 11, color: C.navy, fontWeight: '700' }}>{format(value)}</Text></View><Slider minimumValue={min} maximumValue={max} step={1} value={value} onValueChange={set} minimumTrackTintColor={C.navy} maximumTrackTintColor="#C6C0B5" thumbTintColor={C.amber} /></View>;
}
