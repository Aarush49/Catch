import React from 'react';
import { Text, View } from 'react-native';
import { router } from 'expo-router';
import { LogOut, UserRound } from 'lucide-react-native';
import { Action, C, Eyebrow, Header, Screen, styles } from '../components/tally';
import { useAuth } from '../store/AuthProvider';

export default function Profile() {
  const { user, signOut } = useAuth();
  const logout = async () => {
    await signOut();
    router.replace('/login');
  };

  return <Screen>
    <Header title="Your profile" back="/home" showProfile={false} />
    <Eyebrow>YOUR ACCOUNT</Eyebrow>
    <Text style={styles.h1}>A little{`\n`}about you.</Text>
    <View style={{ alignItems: 'center', paddingVertical: 28 }}>
      <View style={{ width: 88, height: 88, borderRadius: 30, backgroundColor: '#DCE4E8', alignItems: 'center', justifyContent: 'center', marginBottom: 13 }}>
        <UserRound size={38} color={C.navy} />
      </View>
      <Text style={{ fontFamily: 'Georgia', fontSize: 25, color: C.navy }}>{user?.name || 'Your Tally profile'}</Text>
      <Text style={[styles.body, { marginTop: 5 }]}>{user?.email || 'No email on file'}</Text>
    </View>
    <View style={[styles.panel, { marginBottom: 20 }]}>
      <Eyebrow>YOUR PRIVACY</Eyebrow>
      <Text style={{ fontSize: 12, lineHeight: 18, color: C.ink }}>Your Tally activity is stored on this device. You’re in control of your account and can log out whenever you like.</Text>
    </View>
    <Action onPress={logout} kind="danger"><View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><LogOut size={16} color={C.tomato} /><Text style={{ color: C.tomato, fontSize: 13, fontWeight: '700' }}>Log out</Text></View></Action>
  </Screen>;
}
