import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Alert, Pressable, Text, TextInput, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { Camera, Plus, Trash2, Upload, X } from 'lucide-react-native';
import * as ImagePicker from 'expo-image-picker';
import { Action, C, Eyebrow, Header, Money, Screen, styles, money } from '../components/tally';
import { categories, mockReceipts, type LineItem, type Receipt } from '../data/mock';
import { useTally } from '../store/TallyProvider';

export default function Scan() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const { receipts, setReceipts } = useTally();
  const existing = receipts.find((item) => item.id === id);
  const [step, setStep] = useState<'capture' | 'processing' | 'review'>(existing ? 'review' : 'capture');
  const [receipt, setReceipt] = useState<Receipt | null>(existing ? JSON.parse(JSON.stringify(existing)) : null);
  const [remaining, setRemaining] = useState(0);
  const sum = useMemo(() => receipt?.items.reduce((total, item) => total + item.price * item.quantity, 0) || 0, [receipt]);

  useEffect(() => {
    if (step !== 'processing') return;
    setRemaining(15);
    const timer = setTimeout(() => { const next = JSON.parse(JSON.stringify(mockReceipts[8])) as Receipt; next.id = `receipt-${Date.now()}`; setReceipt(next); setStep('review'); }, 1500);
    const pulse = setInterval(() => setRemaining((value) => Math.max(0, value - 1)), 100);
    return () => { clearTimeout(timer); clearInterval(pulse); };
  }, [step]);

  const start = () => setStep('processing');
  const capture = async () => { try { const permission = await ImagePicker.requestCameraPermissionsAsync(); if (!permission.granted) { Alert.alert('Camera access needed', 'You can upload a receipt photo instead.'); return; } const result = await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: .7 }); if (!result.canceled) start(); } catch { Alert.alert('Camera unavailable', 'Use Upload instead to choose a receipt photo.'); } };
  const upload = async () => { try { const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: .7 }); if (!result.canceled) start(); } catch { start(); } };
  const update = (itemId: string, field: keyof LineItem, value: unknown) => setReceipt((current) => current ? { ...current, items: current.items.map((item) => item.id === itemId ? { ...item, [field]: value } : item) } : current);
  const save = () => { if (!receipt) return; const next = { ...receipt, total: +(sum + receipt.tax).toFixed(2) }; setReceipts((all) => existing ? all.map((item) => item.id === existing.id ? next : item) : [next, ...all]); router.replace('/home'); };

  if (step === 'capture') return <View style={{ flex: 1, backgroundColor: C.linen, justifyContent: 'center', alignItems: 'center', padding: 20 }}>
    <Pressable onPress={() => router.back()} style={{ position: 'absolute', top: 55, left: 20, width: 42, height: 42, borderRadius: 24, backgroundColor: '#DED8CD', alignItems: 'center', justifyContent: 'center' }}><X color={C.navy} /></Pressable>
    <View style={{ position: 'absolute', top: 62 }}><Text style={{ fontFamily: 'Georgia', fontSize: 22, color: C.navy, fontWeight: '600' }}>Scan a receipt</Text></View>
    <View style={{ height: '48%', width: '76%', borderWidth: 1.5, borderStyle: 'dashed', borderColor: C.navy, backgroundColor: '#F3EEE5', borderRadius: 18, alignItems: 'center', justifyContent: 'center', gap: 11 }}>
      <Camera color={C.navy} size={30} />
      <Text style={{ fontSize: 11, color: C.muted }}>Point your camera at a receipt</Text>
      <Text style={{ position: 'absolute', top: 12, color: C.navy, fontSize: 9, letterSpacing: 1.2, fontWeight: '700' }}>FIT YOUR RECEIPT HERE</Text>
    </View>
    <View style={{ position: 'absolute', bottom: 45, alignItems: 'center', gap: 12 }}>
      <Text style={{ fontSize: 12, color: C.muted }}>We’ll pick out the items for you.</Text>
      <Pressable onPress={capture} style={{ height: 68, width: 68, borderRadius: 40, borderWidth: 3, borderColor: C.navy, backgroundColor: C.amber, alignItems: 'center', justifyContent: 'center' }}><View style={{ height: 48, width: 48, borderRadius: 28, borderWidth: 2, borderColor: '#846313' }} /></Pressable>
      <Pressable onPress={upload} style={{ padding: 8, flexDirection: 'row', gap: 6 }}><Upload size={14} color={C.navy} /><Text style={{ fontSize: 12, color: C.navy, textDecorationLine: 'underline' }}>Upload instead</Text></Pressable>
    </View>
  </View>;

  if (step === 'processing') return <Screen><View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 100 }}><View style={{ height: 76, width: 76, borderRadius: 24, backgroundColor: '#DCE4E8', alignItems: 'center', justifyContent: 'center', marginBottom: 22 }}><ActivityIndicator color={C.navy} /></View><Eyebrow>A MOMENT PLEASE</Eyebrow><Text style={[styles.h1, { textAlign: 'center' }]}>Reading your{`\n`}receipt.</Text><Text style={[styles.body, { marginTop: 12 }]}>Finding the little details for you…</Text><View style={{ width: 210, height: 7, borderRadius: 5, backgroundColor: '#D8D3C9', marginTop: 20, overflow: 'hidden' }}><View style={{ height: 7, width: `${100 - remaining * 6}%`, backgroundColor: C.navy }} /></View><Text style={[styles.tiny, { marginTop: 10 }]}>Usually takes about 1.5 seconds</Text></View></Screen>;
  if (!receipt) return <Screen><Header title="Review receipt" /><Text>No receipt to review.</Text></Screen>;

  return <Screen><Header title="Review receipt" back="/" /><View style={{ flexDirection: 'row', gap: 12, marginBottom: 14 }}><View style={{ flex: 1 }}><Eyebrow>STORE</Eyebrow><TextInput style={styles.textInput} value={receipt.merchant} onChangeText={(merchant) => setReceipt({ ...receipt, merchant })} /></View><View style={{ flex: 1 }}><Eyebrow>DATE</Eyebrow><TextInput style={styles.textInput} value={receipt.date} onChangeText={(date) => setReceipt({ ...receipt, date })} /></View></View><View style={[styles.row, styles.divider, { paddingVertical: 13, flexWrap: 'wrap', gap: 8 }]}><Eyebrow>RUNNING TOTAL</Eyebrow><Money value={sum} size={24} color={C.navy} /><Text style={[styles.tiny, { marginLeft: 'auto' }]}>Receipt total {money(receipt.total)}</Text>{Math.abs(sum + receipt.tax - receipt.total) > .02 && <Text style={{ width: '100%', fontSize: 10, color: C.tomato }}>Check total ({money(sum + receipt.tax - receipt.total)} off)</Text>}</View>{receipt.items.map((item) => <View key={item.id} style={[styles.row, styles.divider, { minHeight: 66, gap: 8 }]}><View style={{ flex: 1 }}><TextInput style={{ fontSize: 12, fontWeight: '700', color: C.ink, padding: 2 }} value={item.name} onChangeText={(name) => update(item.id, 'name', name)} /><Pressable onPress={() => { const index = categories.indexOf(item.category); update(item.id, 'category', categories[(index + 1) % categories.length]); }}><Text style={styles.tiny}>{item.category} · tap to change{item.confidence ? ' · Check this' : ''}</Text></Pressable></View><TextInput style={{ width: 70, textAlign: 'right', fontSize: 12, color: C.navy }} keyboardType="decimal-pad" value={String(item.price)} onChangeText={(value) => update(item.id, 'price', Number(value) || 0)} /><Pressable onPress={() => setReceipt({ ...receipt, items: receipt.items.filter((candidate) => candidate.id !== item.id) })} hitSlop={12}><Trash2 size={17} color="#A37C75" /></Pressable></View>)}<Pressable onPress={() => setReceipt({ ...receipt, items: [...receipt.items, { id: `new-${Date.now()}`, name: 'New item', price: 0, quantity: 1, category: 'Other', carbon: .3 }] })} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingVertical: 13 }}><Plus size={17} color={C.navy} /><Text style={{ fontSize: 12, fontWeight: '700', color: C.navy }}>Add another item</Text></Pressable><Action onPress={save} style={{ marginTop: 12 }}>Save receipt  ✓</Action></Screen>;
}
