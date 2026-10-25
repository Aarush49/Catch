import React from 'react';
import { Redirect } from 'expo-router';
import { useAuth } from '../store/AuthProvider';

export default function Index() {
  const { user } = useAuth();
  return <Redirect href={user ? (user.needsOnboarding ? '/onboarding' : '/home') : '/login'} />;
}
