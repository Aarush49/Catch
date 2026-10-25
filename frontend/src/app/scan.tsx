import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Alert, Animated, Dimensions, Easing, Pressable, Text, TextInput, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { ArrowDown, Camera, Plus, Trash2, Upload, X } from 'lucide-react-native';
import * as ImagePicker from 'expo-image-picker';
import * as ImageManipulator from 'expo-image-manipulator';
import { CameraView, useCameraPermissions, type CameraView as CameraViewType } from 'expo-camera';
import { Action, C, Eyebrow, Header, Money, Screen, styles, money } from '../components/tally';
import { categories, type LineItem, type Receipt } from '../data/mock';
import { useTally } from '../store/TallyProvider';
import { scanReceipt } from '../services/receipts';

export default function Scan() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const { receipts, setReceipts, saveReceipt } = useTally();
  const existing = receipts.find((item) => item.id === id);
  const [step, setStep] = useState<'capture' | 'processing' | 'review'>(existing ? 'review' : 'capture');
  const [receipt, setReceipt] = useState<Receipt | null>(existing ? JSON.parse(JSON.stringify(existing)) : null);
  const [remaining, setRemaining] = useState(0);
  const [scanError, setScanError] = useState('');
  const [lastImage, setLastImage] = useState('');
  const [reviewWarning, setReviewWarning] = useState('');
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraPermission, requestCameraPermission] = useCameraPermissions();
  const cameraRef = React.useRef<CameraViewType>(null);
  const captureOffset = useRef(new Animated.Value(Dimensions.get('window').height)).current;
  const closingCapture = useRef(false);
  const sum = useMemo(() => receipt?.items.reduce((total, item) => total + item.price * item.quantity, 0) || 0, [receipt]);

  useEffect(() => {
    if (step !== 'processing') return;
    setRemaining(15);
    const pulse = setInterval(() => setRemaining((value) => Math.max(0, value - 1)), 100);
    return () => clearInterval(pulse);
  }, [step]);

  useEffect(() => {
    if (step !== 'capture') return;
    const timer = setTimeout(() => Animated.timing(captureOffset, { toValue: 0, duration: 390, easing: Easing.out(Easing.cubic), useNativeDriver: true }).start(), 20);
    return () => { clearTimeout(timer); captureOffset.stopAnimation(); };
  }, [step]);

  const start = async (uri: string) => {
    setLastImage(uri); setScanError(''); setStep('processing');
    try {
      const image = await ImageManipulator.manipulateAsync(uri, [{ resize: { width: 1600 } }], { compress: .7, format: ImageManipulator.SaveFormat.JPEG });
      const parsed = await scanReceipt(image.uri);
      setReceipt(parsed); setReviewWarning(parsed.reviewReason || ''); setStep('review');
    } catch (error) { setScanError(error instanceof Error ? error.message : 'Could not read this receipt.'); }
  };
  const capture = async () => {
    try {
      if (!cameraPermission?.granted) {
        const permission = await requestCameraPermission();
        if (!permission.granted) { Alert.alert('Camera access needed', 'Allow camera access in your device settings, or choose a photo from your library.'); return; }
      }
      if (!cameraActive) { setCameraActive(true); return; }
      const photo = await cameraRef.current?.takePictureAsync({ quality: .7 });
      if (photo?.uri) await start(photo.uri);
    } catch (error) { Alert.alert('Camera unavailable', error instanceof Error ? error.message : 'Please try again or choose a photo from your library.'); }
  };
  const upload = async () => { try { const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: .7 }); if (!result.canceled) await start(result.assets[0].uri); } catch (error) { setScanError(error instanceof Error ? error.message : 'Could not open that image.'); setStep('processing'); } };
  const closeCapture = () => {
    if (closingCapture.current) return;
    closingCapture.current = true;
    Animated.timing(captureOffset, { toValue: Dimensions.get('window').height, duration: 360, easing: Easing.inOut(Easing.cubic), useNativeDriver: true }).start(() => router.back());
  };
  const update = (itemId: string, field: keyof LineItem, value: unknown) => setReceipt((current) => current ? { ...current, items: current.items.map((item) => item.id === itemId ? { ...item, [field]: value } : item) } : current);
  const save = async () => { if (!receipt) return; const next = { ...receipt, total: +(sum + receipt.tax).toFixed(2) }; try { if (existing) setReceipts((all) => all.map((item) => item.id === existing.id ? next : item)); else await saveReceipt(next); router.replace('/home'); } catch (error) { Alert.alert('Could not save receipt', error instanceof Error ? error.message : 'Please try again.'); } };

  if (step === 'capture') return <Animated.View style={{ flex: 1, backgroundColor: C.linen, justifyContent: 'center', alignItems: 'center', padding: 20, transform: [{ translateY: captureOffset }] }}>
    <Pressable accessibilityRole="button" accessibilityLabel="Close camera" onPress={closeCapture} style={{ position: 'absolute', top: 55, left: '50%', marginLeft: -32, width: 64, height: 64, borderRadius: 34, borderWidth: 6, borderColor: C.amber, borderBottomWidth: 9, borderBottomColor: '#002B53', backgroundColor: C.navy, alignItems: 'center', justifyContent: 'center' }}><ArrowDown color="white" size={25} strokeWidth={2.7} /></Pressable>
    <View style={{ position: 'absolute', top: 128 }}><Text style={{ fontFamily: 'Georgia', fontSize: 22, color: C.navy, fontWeight: '600' }}>Scan a receipt</Text></View>
    <View style={{ height: '48%', width: '76%', borderWidth: 1.5, borderStyle: 'dashed', borderColor: C.navy, backgroundColor: '#F3EEE5', borderRadius: 18, overflow: 'hidden', alignItems: 'center', justifyContent: 'center', gap: 11 }}>
      {cameraActive && cameraPermission?.granted ? <CameraView ref={cameraRef} style={{ width: '100%', height: '100%' }} facing="back" /> : <><Camera color={C.navy} size={30} /><Text style={{ fontSize: 11, color: C.muted }}>Tap the camera button to start</Text></>}
      <Text style={{ position: 'absolute', top: 12, color: cameraActive ? 'white' : C.navy, fontSize: 9, letterSpacing: 1.2, fontWeight: '700' }}>FIT YOUR RECEIPT HERE</Text>
    </View>
    <View style={{ position: 'absolute', bottom: 35, alignItems: 'center', gap: 10 }}>
      <Text style={{ fontSize: 12, color: C.muted }}>We’ll pick out the items for you.</Text>
      <Pressable accessibilityRole="button" accessibilityLabel={cameraActive ? 'Take receipt photo' : 'Open camera'} onPress={capture} style={{ height: 68, width: 68, borderRadius: 40, borderWidth: 3, borderColor: C.navy, backgroundColor: C.amber, alignItems: 'center', justifyContent: 'center' }}><View style={{ height: 48, width: 48, borderRadius: 28, borderWidth: 2, borderColor: '#846313', alignItems: 'center', justifyContent: 'center' }}>{cameraActive && <Camera size={20} color={C.navy} />}</View></Pressable>
      <Pressable accessibilityRole="button" accessibilityLabel="Choose receipt photo from library" onPress={upload} style={{ height: 46, minWidth: 205, borderRadius: 15, borderWidth: 1, borderColor: C.navy, backgroundColor: '#FFFAF1', alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }}><Upload size={15} color={C.navy} /><Text style={{ fontSize: 12, color: C.navy, fontWeight: '700' }}>Choose from library</Text></Pressable>
    </View>
  </Animated.View>;

  if (step === 'processing') return <Screen><View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 100 }}><View style={{ height: 76, width: 76, borderRadius: 24, backgroundColor: '#DCE4E8', alignItems: 'center', justifyContent: 'center', marginBottom: 22 }}>{scanError ? <X color={C.tomato} /> : <ActivityIndicator color={C.navy} />}</View><Eyebrow>{scanError ? 'LET’S TRY THAT AGAIN' : 'A MOMENT PLEASE'}</Eyebrow><Text style={[styles.h1, { textAlign: 'center' }]}>{scanError ? 'We couldn’t read that receipt.' : <>Reading your{`\n`}receipt.</>}</Text><Text style={[styles.body, { marginTop: 12, textAlign: 'center' }]}>{scanError || 'Finding the little details for you…'}</Text>{!scanError && <View style={{ width: 210, height: 7, borderRadius: 5, backgroundColor: '#D8D3C9', marginTop: 20, overflow: 'hidden' }}><View style={{ height: 7, width: `${100 - remaining * 6}%`, backgroundColor: C.navy }} /></View>}{scanError && <View style={{ width: '100%', gap: 10, marginTop: 20 }}><Action onPress={() => start(lastImage)}>Retry</Action><Action kind="secondary" onPress={() => { setReceipt({ id: `manual-${Date.now()}`, merchant: '', date: new Date().toISOString().slice(0, 10), tax: 0, total: 0, items: [] }); setStep('review'); }}>Enter manually</Action></View>}</View></Screen>;
  if (!receipt) return <Screen><Header title="Review receipt" /><Text>No receipt to review.</Text></Screen>;

  return <Screen><Header title="Review receipt" back="/" /><View style={{ flexDirection: 'row', gap: 12, marginBottom: 14 }}><View style={{ flex: 1 }}><Eyebrow>STORE</Eyebrow><TextInput style={styles.textInput} value={receipt.merchant} onChangeText={(merchant) => setReceipt({ ...receipt, merchant })} /></View><View style={{ flex: 1 }}><Eyebrow>DATE</Eyebrow><TextInput style={styles.textInput} value={receipt.date} onChangeText={(date) => setReceipt({ ...receipt, date })} /></View></View><View style={[styles.row, styles.divider, { paddingVertical: 13, flexWrap: 'wrap', gap: 8 }]}><Eyebrow>RUNNING TOTAL</Eyebrow><Money value={sum} size={24} color={C.navy} /><Text style={[styles.tiny, { marginLeft: 'auto' }]}>Receipt total {money(receipt.total)}</Text>{Math.abs(sum + receipt.tax - receipt.total) > .02 && <Text style={{ width: '100%', fontSize: 10, color: C.tomato }}>Check total ({money(sum + receipt.tax - receipt.total)} off)</Text>}</View>{receipt.items.map((item) => <View key={item.id} style={[styles.row, styles.divider, { minHeight: 66, gap: 8 }]}><View style={{ flex: 1 }}><TextInput style={{ fontSize: 12, fontWeight: '700', color: C.ink, padding: 2 }} value={item.name} onChangeText={(name) => update(item.id, 'name', name)} /><Pressable onPress={() => { const index = categories.indexOf(item.category); update(item.id, 'category', categories[(index + 1) % categories.length]); }}><Text style={styles.tiny}>{item.category} · tap to change{item.confidence ? ' · Check this' : ''}</Text></Pressable></View><TextInput style={{ width: 70, textAlign: 'right', fontSize: 12, color: C.navy }} keyboardType="decimal-pad" value={String(item.price)} onChangeText={(value) => update(item.id, 'price', Number(value) || 0)} /><Pressable onPress={() => setReceipt({ ...receipt, items: receipt.items.filter((candidate) => candidate.id !== item.id) })} hitSlop={12}><Trash2 size={17} color="#A37C75" /></Pressable></View>)}<Pressable onPress={() => setReceipt({ ...receipt, items: [...receipt.items, { id: `new-${Date.now()}`, name: 'New item', price: 0, quantity: 1, category: 'Other', carbon: .3 }] })} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingVertical: 13 }}><Plus size={17} color={C.navy} /><Text style={{ fontSize: 12, fontWeight: '700', color: C.navy }}>Add another item</Text></Pressable><Action onPress={save} style={{ marginTop: 12 }}>Save receipt  ✓</Action></Screen>;
}


