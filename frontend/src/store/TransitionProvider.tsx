import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import { Animated, Dimensions, Easing, Image, Text, View } from 'react-native';
import { router } from 'expo-router';

type RevealKind = 'profile' | 'calendar';
type OverlayKind = RevealKind | 'splash' | 'morph';
type Origin = { x: number; y: number; width: number; height: number };
type TransitionApi = { goTo: (route: '/profile' | '/calendar', kind: RevealKind) => void; goBack: (route?: string) => void; playLogin: (callback: () => Promise<void>) => void; morphTo: (route: string | { pathname: string; params?: Record<string, string> }, origin: Origin) => void; registerBack: (handler: (route?: string, done?: () => void) => void) => () => void };
const Context = createContext<TransitionApi | null>(null);
const duration = 380;

export function TransitionProvider({ children }: { children: React.ReactNode }) {
  const [overlay, setOverlay] = useState<null | { kind: OverlayKind; phase: 'in' | 'out' }>(null);
  const progress = useRef(new Animated.Value(0)).current;
  const splashY = useRef(new Animated.Value(-Dimensions.get('window').height)).current;
  const locked = useRef(false);
  const backHandler = useRef<((route?: string, done?: () => void) => void) | null>(null);
  const morphLeft = useRef(new Animated.Value(0)).current;
  const morphTop = useRef(new Animated.Value(0)).current;
  const morphWidth = useRef(new Animated.Value(0)).current;
  const morphHeight = useRef(new Animated.Value(0)).current;
  const morphOpacity = useRef(new Animated.Value(1)).current;
  const goTo = (route: '/profile' | '/calendar', kind: RevealKind) => {
    if (locked.current) return;
    locked.current = true;
    const revealDuration = kind === 'calendar' ? 620 : duration;
    progress.setValue(0);
    setOverlay({ kind, phase: 'in' });
    Animated.timing(progress, { toValue: 1, duration: revealDuration, easing: Easing.out(Easing.cubic), useNativeDriver: true }).start(() => {
      router.push(route as never);
      setOverlay({ kind, phase: 'out' });
      Animated.timing(progress, { toValue: 0, duration: revealDuration * .9, easing: Easing.inOut(Easing.cubic), useNativeDriver: true }).start(() => { setOverlay(null); locked.current = false; });
    });
  };
  const goBack = (route?: string) => {
    if (locked.current) return;
    locked.current = true;
    if (backHandler.current) backHandler.current(route, () => { locked.current = false; });
    else { if (route) router.replace(route as never); else router.back(); locked.current = false; }
  };
  const registerBack = useCallback((handler: (route?: string, done?: () => void) => void) => {
    backHandler.current = handler;
    return () => { if (backHandler.current === handler) backHandler.current = null; };
  }, []);
  const morphTo = (route: string | { pathname: string; params?: Record<string, string> }, origin: Origin) => {
    if (locked.current) return;
    locked.current = true;
    const width = Dimensions.get('window').width;
    const height = Dimensions.get('window').height;
    morphLeft.setValue(origin.x); morphTop.setValue(origin.y);
    morphWidth.setValue(origin.width); morphHeight.setValue(origin.height); morphOpacity.setValue(1);
    setOverlay({ kind: 'morph', phase: 'in' });
    Animated.parallel([
      Animated.timing(morphTop, { toValue: 0, duration: 110, easing: Easing.out(Easing.cubic), useNativeDriver: false }),
      Animated.timing(morphHeight, { toValue: height, duration: 110, easing: Easing.out(Easing.cubic), useNativeDriver: false }),
    ]).start(() => Animated.parallel([
        Animated.timing(morphLeft, { toValue: 0, duration: 180, easing: Easing.inOut(Easing.cubic), useNativeDriver: false }),
        Animated.timing(morphWidth, { toValue: width, duration: 180, easing: Easing.inOut(Easing.cubic), useNativeDriver: false }),
    ]).start(() => {
      router.push(route as never);
      setTimeout(() => Animated.timing(morphOpacity, { toValue: 0, duration: 220, easing: Easing.out(Easing.cubic), useNativeDriver: true }).start(() => {
        setOverlay(null); morphOpacity.setValue(1); locked.current = false;
      }), 35);
    }));
  };
  const playLogin = (callback: () => Promise<void>) => {
    if (locked.current) return;
    locked.current = true;
    splashY.setValue(-Dimensions.get('window').height);
    setOverlay({ kind: 'splash', phase: 'in' });
    Animated.timing(splashY, { toValue: 0, duration: 500, easing: Easing.out(Easing.cubic), useNativeDriver: true }).start(() => {
      setTimeout(async () => {
        await callback();
        setOverlay({ kind: 'splash', phase: 'out' });
        setTimeout(() => Animated.timing(splashY, { toValue: Dimensions.get('window').height, duration: 520, easing: Easing.inOut(Easing.cubic), useNativeDriver: true }).start(() => { setOverlay(null); locked.current = false; }), 100);
      }, 2000);
    });
  };
  const value = useMemo(() => ({ goTo, goBack, playLogin, morphTo, registerBack }), [overlay]);
  const width = Dimensions.get('window').width;
  const height = Dimensions.get('window').height;
  const size = Math.ceil(Math.hypot(width, height) * 2);
  const scale = progress.interpolate({ inputRange: [0, 1], outputRange: [0, 1] });
  return <Context.Provider value={value}>
    <View style={{ flex: 1 }}>{children}</View>
    {overlay?.kind === 'splash' && <Animated.View pointerEvents="none" style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: '#003A70', transform: [{ translateY: splashY }], alignItems: 'center', justifyContent: 'center' }}>
      <Image source={require('../../assets/catch-logo.png')} resizeMode="contain" style={{ width: 130, height: 130, marginBottom: 16 }} />
      <Text style={{ fontSize: 27, color: '#FBBF24', fontWeight: '700' }}>CATch</Text>
    </Animated.View>}
    {overlay?.kind === 'morph' && <Animated.View pointerEvents="none" style={{ position: 'absolute', left: morphLeft, top: morphTop, width: morphWidth, height: morphHeight, opacity: morphOpacity, backgroundColor: '#EAE4D9', borderRadius: 18 }} />}
    {overlay && overlay.kind !== 'splash' && <Animated.View pointerEvents="none" style={{ position: 'absolute', top: overlay.kind === 'calendar' ? (height - size) / 2 : overlay.phase === 'in' ? -size / 2 : height - size / 2, left: overlay.kind === 'calendar' ? (width - size) / 2 : overlay.phase === 'in' ? undefined : -size / 2, right: overlay.kind === 'calendar' ? undefined : overlay.phase === 'in' ? -size / 2 : undefined, width: size, height: size, borderRadius: size / 2, backgroundColor: overlay.kind === 'calendar' ? '#F5CE58' : '#EAE4D9', transform: [{ scale }] }} />}
  </Context.Provider>;
}

export function useTransitions() {
  const value = useContext(Context);
  if (!value) throw new Error('useTransitions must be used inside TransitionProvider');
  return value;
}



