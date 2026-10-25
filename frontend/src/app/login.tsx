import React, { useState } from 'react';
import { Alert } from 'react-native';
import { router } from 'expo-router';
import { AuthScreen } from '../components/AuthScreen';
import { useAuth } from '../store/AuthProvider';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const { signIn } = useAuth();
  const submit = async () => {
    if (!email.trim() || !password) return Alert.alert('A couple details are missing', 'Enter your email and password to continue.');
    await signIn(email.trim(), password);
    router.replace('/home');
  };
  return <AuthScreen mode="login" email={email} password={password} onEmailChange={setEmail} onPasswordChange={setPassword} onSubmit={submit} onSwitch={() => router.replace('/signup')} />;
}
