import React, { useCallback, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import { Flame, Landmark, LogOut, Mail, UserRound } from 'lucide-react-native';
import { Action, C, Eyebrow, Header, Screen, dateLabel, styles } from '../components/tally';
import { connectDemoBank, getBankLink, refreshBank, type BankLink } from '../services/bank';
import { useAuth } from '../store/AuthProvider';
import { useTally } from '../store/TallyProvider';

export default function Profile() {
  const { user, signOut } = useAuth();
  const { receipts } = useTally();
  const canBank = !!user && user.id !== 'demo';
  const [link, setLink] = useState<BankLink | null | undefined>(undefined);
  const [busy, setBusy] = useState<'connect' | 'refresh' | null>(null);
  const [bankNote, setBankNote] = useState('');
  const [bankError, setBankError] = useState('');
  const username = user?.email.split('@')[0] || 'catch-user';
  const days = new Set(receipts.map((receipt) => receipt.date));
  let streak = 0;
  if (days.size) {
    const cursor = new Date(`${[...days].sort().at(-1)}T12:00:00`);
    while (days.has(cursor.toISOString().slice(0, 10))) { streak++; cursor.setDate(cursor.getDate() - 1); }
  }
  const loadLink = useCallback(() => {
    if (!canBank) { setLink(null); return; }
    getBankLink().then(setLink, (error) => { setLink(null); setBankError(error instanceof Error ? error.message : 'Could not load your bank connection.'); });
  }, [canBank]);
  useFocusEffect(loadLink);

  const runBank = async (kind: 'connect' | 'refresh') => {
    if (busy) return;
    setBusy(kind); setBankNote(''); setBankError('');
    try {
      const result = kind === 'connect' ? await connectDemoBank() : await refreshBank();
      setLink(await getBankLink());
      setBankNote(kind === 'connect' && result.created
        ? `Demo bank connected · ${result.count} items imported (purchases, a paycheck and monthly bills).`
        : `Up to date · ${result.count} items imported.`);
    } catch (error) {
      setBankError(error instanceof Error ? error.message : 'The bank request failed. Please try again.');
    } finally { setBusy(null); }
  };
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
      <Text style={{ fontFamily: 'Georgia', fontSize: 25, color: C.navy }}>{user?.name || 'Your Catch profile'}</Text>
      <Text style={[styles.body, { marginTop: 5 }]}>@{username}</Text>
      <Text style={[styles.body, { marginTop: 5 }]}>{user?.email || 'No email on file'}</Text>
    </View>
    <View style={{ flexDirection: 'row', gap: 10, marginBottom: 20 }}>
      <View style={[styles.panel, { flex: 1, alignItems: 'center' }]}><Flame size={20} color={C.tomato} /><Text style={{ fontFamily: 'Georgia', fontSize: 26, color: C.navy, marginTop: 6 }}>{streak}</Text><Text style={styles.tiny}>DAY STREAK</Text></View>
      <View style={[styles.panel, { flex: 1, alignItems: 'center' }]}><Mail size={20} color={C.navy} /><Text style={{ fontFamily: 'Georgia', fontSize: 26, color: C.navy, marginTop: 6 }}>{receipts.length}</Text><Text style={styles.tiny}>RECEIPTS</Text></View>
    </View>
    <View style={[styles.panel, { marginBottom: 20, gap: 10 }]}>
      <View style={[styles.row, { gap: 8 }]}><Landmark size={16} color={C.navy} /><Eyebrow>YOUR BANK</Eyebrow></View>
      {!canBank ? <Text style={{ fontSize: 12, lineHeight: 18, color: C.ink }}>Sign in with an account to connect a bank. Demo mode keeps everything on this device.</Text>
        : link === undefined ? <ActivityIndicator color={C.navy} />
        : link ? <>
          <Text style={{ fontSize: 12, lineHeight: 18, color: C.ink }}><Text style={{ color: C.amber, fontWeight: '700' }}>Cat</Text>ch demo checking is connected (since {dateLabel(link.linkedAt.slice(0, 10))}). Its purchases, paychecks and savings show on your Dashboard, and its bills feed Predict.</Text>
          <Action onPress={() => runBank('refresh')} kind="secondary">{busy === 'refresh' ? 'Refreshing…' : 'Refresh bank activity'}</Action>
        </> : <>
          <Text style={{ fontSize: 12, lineHeight: 18, color: C.ink }}>Try <Text style={{ color: C.amber, fontWeight: '700' }}>Cat</Text>ch with a sandbox checking account (Capital One Nessie) that comes with a month of sample purchases, a paycheck and monthly bills, plus a savings account for your swap savings. No real bank details needed.</Text>
          <Action onPress={() => runBank('connect')}>{busy === 'connect' ? 'Connecting… (up to 20 seconds)' : 'Connect demo bank'}</Action>
        </>}
      {!!bankNote && <Text style={[styles.tiny, { color: '#157536' }]}>{bankNote}</Text>}
      {!!bankError && <Text style={[styles.tiny, { color: C.tomato }]}>{bankError}</Text>}
    </View>
    <View style={[styles.panel, { marginBottom: 20 }]}>
      <Eyebrow>YOUR PRIVACY</Eyebrow>
      <Text style={{ fontSize: 12, lineHeight: 18, color: C.ink }}>Your receipts, list and bank activity are saved to your <Text style={{ color: C.amber, fontWeight: '700' }}>Cat</Text>ch account, visible only to you. You can log out whenever you like.</Text>
    </View>
    <Action onPress={logout} kind="danger"><View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><LogOut size={16} color={C.tomato} /><Text style={{ color: C.tomato, fontSize: 13, fontWeight: '700' }}>Log out</Text></View></Action>
  </Screen>;
}
