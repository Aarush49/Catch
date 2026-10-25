import React, { useEffect, useState } from 'react';
import { Image, Text, View } from 'react-native';
import { Stack } from 'expo-router';
import { usePathname } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import * as SplashScreen from 'expo-splash-screen';
import { useFonts, DMSans_400Regular, DMSans_500Medium, DMSans_700Bold } from '@expo-google-fonts/dm-sans';
import { AuthProvider, useAuth } from '../store/AuthProvider';
import { TallyProvider, useTally } from '../store/TallyProvider';
import { TransitionProvider } from '../store/TransitionProvider';
import { BottomNav } from '../components/tally';

SplashScreen.preventAutoHideAsync().catch(() => {});

const screenOptions = { headerShown: false, animation: 'none' as const, contentStyle: { backgroundColor: '#EAE4D9' } };

export default function RootLayout() {
  const [fontsLoaded] = useFonts({ DMSans_400Regular, DMSans_500Medium, DMSans_700Bold });
  return <AuthProvider><TallyProvider><RootNavigator fontsLoaded={fontsLoaded} /></TallyProvider></AuthProvider>;
}

function RootNavigator({ fontsLoaded }: { fontsLoaded: boolean }) {
  const { ready: storeHydrated } = useTally();
  const { user, hydrated: authHydrated } = useAuth();
  const pathname = usePathname();
  const [minimumSplashElapsed, setMinimumSplashElapsed] = useState(false);
  const resourcesReady = fontsLoaded && storeHydrated && authHydrated;
  const isReady = resourcesReady && minimumSplashElapsed;

  useEffect(() => {
    const timer = setTimeout(() => setMinimumSplashElapsed(true), 1000);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (resourcesReady) SplashScreen.hideAsync().catch(() => {});
  }, [resourcesReady]);

  if (!isReady) return <View style={{ flex: 1, backgroundColor: '#EAE4D9', alignItems: 'center', justifyContent: 'center' }}>
    <Image source={require('../../assets/catch-logo.png')} resizeMode="contain" style={{ height: 150, width: 166, marginBottom: 12 }} />
    <Text style={{ fontFamily: fontsLoaded ? 'DMSans_700Bold' : undefined, fontSize: 28, color: '#003A70' }}>CATch</Text>
  </View>;

  return <>
    <StatusBar style="dark" />
    <TransitionProvider><Stack screenOptions={screenOptions}>
      <Stack.Screen name="index" />
      <Stack.Protected guard={!user}>
        <Stack.Screen name="login" />
        <Stack.Screen name="signup" />
      </Stack.Protected>
      <Stack.Protected guard={Boolean(user?.needsOnboarding)}>
        <Stack.Screen name="onboarding" />
      </Stack.Protected>
      <Stack.Protected guard={Boolean(user && !user.needsOnboarding)}>
        <Stack.Screen name="home" />
        <Stack.Screen name="dashboard" />
        <Stack.Screen name="scan" options={{ presentation: 'transparentModal', contentStyle: { backgroundColor: 'transparent' } }} />
        <Stack.Screen name="receipt/[id]" />
        <Stack.Screen name="shopping" />
        <Stack.Screen name="compare" />
        <Stack.Screen name="predict" />
        <Stack.Screen name="rewind" />
        <Stack.Screen name="group" />
        <Stack.Screen name="calendar" />
        <Stack.Screen name="profile" />
      </Stack.Protected>
    </Stack></TransitionProvider>
    {Boolean(user) && pathname !== '/scan' && <BottomNav />}
  </>;
}
