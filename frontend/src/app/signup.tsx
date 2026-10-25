import React, { useState } from 'react';
import { Alert } from 'react-native';
import { router } from 'expo-router';
import { AuthScreen } from '../components/AuthScreen';
import { useAuth } from '../store/AuthProvider';

export default function Signup() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const { signUp } = useAuth();
  const submit = async () => {
    if (!name.trim() || !email.trim() || password.length < 8) return Alert.alert('Check your details', 'Add your name, a valid email, and a password with at least 8 characters.');
    await signUp(name.trim(), email.trim(), password);
    router.replace('/home');
  };
  return <AuthScreen mode="signup" name={name} email={email} password={password} onNameChange={setName} onEmailChange={setEmail} onPasswordChange={setPassword} onSubmit={submit} onSwitch={() => router.replace('/login')} />;
}
