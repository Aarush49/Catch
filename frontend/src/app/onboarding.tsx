import React, { useState } from 'react';
import { Image, Pressable, Text, View } from 'react-native';
import { router } from 'expo-router';
import { Camera, Leaf, TrendingUp } from 'lucide-react-native';
import { C } from '../components/tally';
import { useAuth } from '../store/AuthProvider';

const steps = [
  { icon: Camera, title: 'Catch every purchase.', copy: 'Scan a receipt and Catch turns each item into a clear spending record.' },
  { icon: Leaf, title: 'See all three costs.', copy: 'Compare what you paid, its future value, and its estimated carbon impact.' },
  { icon: TrendingUp, title: 'Make the next choice count.', copy: 'Explore swaps, predictions, lists, and groups as your history grows.' },
];

export default function Onboarding() {
  const [step, setStep] = useState(0);
  const { user, completeOnboarding } = useAuth();
  const current = steps[step];
  const Icon = current.icon;
  const finish = async () => {
    await completeOnboarding();
    router.replace('/home');
  };

  return <View style={{ flex: 1, backgroundColor: C.linen, paddingHorizontal: 26, paddingVertical: 42, alignItems: 'center', justifyContent: 'center' }}>
    <Image source={require('../../assets/catch-logo.png')} resizeMode="contain" style={{ width: 210, height: 188, marginBottom: 18 }} />
    <View style={{ width: 54, height: 54, borderRadius: 18, backgroundColor: step === 1 ? '#D8EAD8' : step === 2 ? '#F5D768' : '#DCE4E8', alignItems: 'center', justifyContent: 'center', marginBottom: 18 }}><Icon size={25} color={C.navy} /></View>
    <Text style={{ fontFamily: 'Georgia', fontSize: 34, lineHeight: 38, color: C.navy, textAlign: 'center' }}>{step === 0 ? `Welcome, ${user?.name || 'friend'}.` : current.title}</Text>
    {step === 0 && <Text style={{ fontFamily: 'Georgia', fontSize: 25, color: C.tomato, fontStyle: 'italic', textAlign: 'center', marginTop: 4 }}>{current.title}</Text>}
    <Text style={{ fontSize: 13, lineHeight: 20, color: C.muted, textAlign: 'center', marginTop: 14, maxWidth: 310 }}>{current.copy}</Text>
    <View style={{ flexDirection: 'row', gap: 7, marginVertical: 26 }}>{steps.map((_, index) => <View key={index} style={{ width: index === step ? 24 : 7, height: 7, borderRadius: 7, backgroundColor: index === step ? C.navy : '#C5C1B8' }} />)}</View>
    <Pressable onPress={() => step === steps.length - 1 ? finish() : setStep(step + 1)} style={({ pressed }) => ({ width: '100%', minHeight: 54, borderRadius: 16, backgroundColor: C.navy, borderBottomWidth: pressed ? 1 : 5, borderBottomColor: '#002B53', transform: [{ translateY: pressed ? 4 : 0 }], alignItems: 'center', justifyContent: 'center' })}><Text style={{ color: 'white', fontSize: 13, fontWeight: '700' }}>{step === steps.length - 1 ? <>Start using <Text style={{ color: C.amber }}>Cat</Text>ch</> : 'Show me more'}</Text></Pressable>
  </View>;
}
