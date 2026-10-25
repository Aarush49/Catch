import React from 'react';
import { Text, View } from 'react-native';
import { router } from 'expo-router';
import { Flame, LogOut, Mail, UserRound } from 'lucide-react-native';
import { Action, C, Eyebrow, Header, Screen, styles } from '../components/tally';
import { useAuth } from '../store/AuthProvider';
import { useTally } from '../store/TallyProvider';

export default function Profile() {
  const { user, signOut } = useAuth();
  const { receipts } = useTally();
  const username = user?.email.split('@')[0] || 'catch-user';
  const days = new Set(receipts.map((receipt) => receipt.date));
  let streak = 0;
  if (days.size) {
    const cursor = new Date(`${[...days].sort().at(-1)}T12:00:00`);
    while (days.has(cursor.toISOString().slice(0, 10))) { streak++; cursor.setDate(cursor.getDate() - 1); }
  }
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
      <Text style={{ fontFamily: 'Georgia', fontSize: 25, color: C.navy }}>{user?.name || 'Your CATch profile'}</Text>
      <Text style={[styles.body, { marginTop: 5 }]}>@{username}</Text>
      <Text style={[styles.body, { marginTop: 5 }]}>{user?.email || 'No email on file'}</Text>
    </View>
    <View style={{ flexDirection: 'row', gap: 10, marginBottom: 20 }}>
      <View style={[styles.panel, { flex: 1, alignItems: 'center' }]}><Flame size={20} color={C.tomato} /><Text style={{ fontFamily: 'Georgia', fontSize: 26, color: C.navy, marginTop: 6 }}>{streak}</Text><Text style={styles.tiny}>DAY STREAK</Text></View>
      <View style={[styles.panel, { flex: 1, alignItems: 'center' }]}><Mail size={20} color={C.navy} /><Text style={{ fontFamily: 'Georgia', fontSize: 26, color: C.navy, marginTop: 6 }}>{receipts.length}</Text><Text style={styles.tiny}>RECEIPTS</Text></View>
    </View>
    <View style={[styles.panel, { marginBottom: 20 }]}>
      <Eyebrow>YOUR PRIVACY</Eyebrow>
      <Text style={{ fontSize: 12, lineHeight: 18, color: C.ink }}>Your CATch activity is stored on this device. You’re in control of your account and can log out whenever you like.</Text>
    </View>
    <Action onPress={logout} kind="danger"><View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><LogOut size={16} color={C.tomato} /><Text style={{ color: C.tomato, fontSize: 13, fontWeight: '700' }}>Log out</Text></View></Action>
  </Screen>;
}
