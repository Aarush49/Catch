import React, { useRef, useState } from 'react';
import { Alert, Animated, Dimensions, View } from 'react-native';
import { router } from 'expo-router';
import { AuthScreen } from '../components/AuthScreen';
import { useAuth } from '../store/AuthProvider';
import { useTransitions } from '../store/TransitionProvider';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const { signIn } = useAuth();
  const submitted = useRef(false);
  const screenX = useRef(new Animated.Value(0)).current;
  const { playLogin } = useTransitions();
  const submit = async () => {
    if (submitted.current) return;
    if (!email.trim() || !password) return Alert.alert('A couple details are missing', 'Enter your email and password to continue.');
    try {
      setError('');
      await signIn(email.trim(), password);
      submitted.current = true;
      Animated.timing(screenX, { toValue: Dimensions.get('window').width, duration: 380, useNativeDriver: true }).start(() => {
        playLogin(async () => { router.replace({ pathname: '/home', params: { intro: '1' } }); });
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to sign in. Check your connection and try again.');
      submitted.current = false;
    }
  };
  return <View style={{ flex: 1, overflow: 'hidden' }}><Animated.View style={{ flex: 1, transform: [{ translateX: screenX }] }}><AuthScreen mode="login" email={email} password={password} error={error} onEmailChange={setEmail} onPasswordChange={setPassword} onSubmit={submit} onSwitch={() => router.replace('/signup')} /></Animated.View></View>;
}
