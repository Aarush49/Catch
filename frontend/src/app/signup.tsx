import React, { useState } from 'react';
import { Alert } from 'react-native';
import { router } from 'expo-router';
import { AuthScreen } from '../components/AuthScreen';
import { useAuth } from '../store/AuthProvider';
import { useTally } from '../store/TallyProvider';

export default function Signup() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const { signUp } = useAuth();
  const { reset } = useTally();
  const submit = async () => {
    if (!name.trim() || !email.trim() || password.length < 8) return Alert.alert('Check your details', 'Add your name, a valid email, and a password with at least 8 characters.');
    try { setError(''); await reset(); await signUp(name.trim(), email.trim(), password); router.replace('/onboarding'); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to create your account. Check your connection and try again.'); }
  };
  return <AuthScreen mode="signup" name={name} email={email} password={password} error={error} onNameChange={setName} onEmailChange={setEmail} onPasswordChange={setPassword} onSubmit={submit} onSwitch={() => router.replace('/login')} />;
}
