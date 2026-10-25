import React, { useState } from 'react';
import { Alert, Pressable, Text, View } from 'react-native';
import { router } from 'expo-router';
import { ChevronDown, ChevronRight, LogOut, Plus, Users } from 'lucide-react-native';
import { Action, C, Header, Money, Screen, SectionTitle, money, styles } from '../components/tally';
import { useTally } from '../store/TallyProvider';
import { useAuth } from '../store/AuthProvider';

type GroupData = { id: string; name: string; subtitle: string; members: { initial: string; name: string; color: string }[] };

export default function Group() {
  const { receipts } = useTally();
  const { user } = useAuth();
  const displayName = user?.name || user?.email.split('@')[0] || 'You';
  const you = { initial: displayName.charAt(0).toUpperCase(), name: displayName, color: '#F5D768' };
  const [groups, setGroups] = useState<GroupData[]>([]);
  const [activeGroup, setActiveGroup] = useState<string | null>(null);
  const [showGroups, setShowGroups] = useState(false);
  const [visibleMember, setVisibleMember] = useState<string | null>(null);
  const [receiptId, setReceiptId] = useState('');
  const [split, setSplit] = useState(false);
  const group = groups.find((item) => item.id === activeGroup);
  const receipt = receipts.find((item) => item.id === receiptId);

  if (!group) return <Screen><Header title="Your people" back="/" showBack={false} /><View style={{ alignItems: 'center', justifyContent: 'center', minHeight: 520 }}><View style={{ height: 86, width: 86, borderRadius: 28, backgroundColor: '#DCE5E2', alignItems: 'center', justifyContent: 'center' }}><Users size={38} color={C.navy} /></View><Text style={[styles.h1, { fontSize: 32, marginTop: 20, textAlign: 'center' }]}>Groups start{`\n`}with your people.</Text><Text style={[styles.body, { textAlign: 'center', marginTop: 10, marginBottom: 24, maxWidth: 280 }]}>Create a fresh group or join one with an invite. Nothing is shared until you choose.</Text><Action onPress={() => { const next = { id: `group-${Date.now()}`, name: 'My group', subtitle: 'A new shared space', members: [you] }; setGroups([next]); setActiveGroup(next.id); }} style={{ width: '100%', marginBottom: 10 }}>Create a group</Action><Action kind="secondary" onPress={() => { const next = { id: `joined-${Date.now()}`, name: 'Friends', subtitle: 'Shared spending', members: [you, { initial: 'M', name: 'Maya', color: '#BDD5C0' }] }; setGroups([next]); setActiveGroup(next.id); }} style={{ width: '100%' }}>Join a group</Action></View></Screen>;

  const leave = () => Alert.alert(`Leave ${group.name}?`, 'You can join it again from the group list.', [{ text: 'Cancel', style: 'cancel' }, { text: 'Leave group', style: 'destructive', onPress: () => { setActiveGroup(null); setReceiptId(''); } }]);
  const perPerson = receipt ? receipt.total / group.members.length : 0;

  return <Screen>
    <Header title="Your people" back="/" showBack={false} />
    <View style={[styles.row, { justifyContent: 'space-between', alignItems: 'flex-start' }]}>
      <View style={{ flexDirection: 'row', marginBottom: 13 }}>
        {group.members.map((member) => <Pressable key={member.name} onPress={() => setVisibleMember(visibleMember === member.name ? null : member.name)} onHoverIn={() => setVisibleMember(member.name)} onHoverOut={() => setVisibleMember(null)} style={{ alignItems: 'center' }}><View style={{ height: 32, width: 32, borderRadius: 20, backgroundColor: member.color, marginLeft: -3, borderWidth: 2, borderColor: C.linen, alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 11, fontWeight: '700', color: C.navy }}>{member.initial}</Text></View>{visibleMember === member.name && <View style={{ position: 'absolute', top: 37, backgroundColor: C.ink, borderRadius: 7, paddingHorizontal: 8, paddingVertical: 5, zIndex: 5 }}><Text style={{ fontSize: 9, color: 'white' }}>{member.name}</Text></View>}</Pressable>)}
      </View>
      <Pressable onPress={() => setShowGroups(!showGroups)} style={[styles.row, { gap: 5, backgroundColor: '#E2DDD3', borderRadius: 10, paddingHorizontal: 9, paddingVertical: 7 }]}><Text style={{ fontSize: 10, color: C.navy, fontWeight: '700' }}>Switch group</Text><ChevronDown size={14} color={C.navy} /></Pressable>
    </View>
    {showGroups && <View style={[styles.panel, { marginBottom: 14 }]}>{groups.map((item) => <Pressable key={item.id} onPress={() => { setActiveGroup(item.id); setShowGroups(false); setReceiptId(''); }} style={[styles.row, { minHeight: 44, gap: 8 }]}><View style={{ flex: 1 }}><Text style={{ fontSize: 11, fontWeight: '700', color: C.ink }}>{item.name}</Text><Text style={styles.tiny}>{item.members.length} members</Text></View>{item.id === activeGroup && <Text style={{ color: C.jungle, fontWeight: '700' }}>✓</Text>}</Pressable>)}<Pressable onPress={() => Alert.alert('Start another group', 'Group invitations are ready for the next backend connection.')} style={[styles.row, { gap: 7, paddingTop: 9, borderTopWidth: 1, borderColor: C.rule }]}><Plus size={15} color={C.navy} /><Text style={{ fontSize: 11, color: C.navy, fontWeight: '700' }}>Create another group</Text></Pressable></View>}

    <Text style={[styles.h1, { fontSize: 39 }]}>{group.name}{`\n`}<Text style={{ color: C.tomato, fontStyle: 'italic' }}>account.</Text></Text>
    <Text style={[styles.body, { marginBottom: 16 }]}>{group.members.length > 1 ? `Shared with ${group.members.slice(1).map((member) => member.name).join(' and ')}` : 'Only you are here. Invite someone when you’re ready.'}</Text>
    {group.members.length > 1 && <View style={{ borderRadius: 19, backgroundColor: C.navy, padding: 16, marginBottom: 18 }}><Text style={{ fontSize: 8, letterSpacing: 1, color: '#F6D968', fontWeight: '700' }}>LOOKING GOOD</Text><Text style={{ fontFamily: 'Georgia', fontSize: 20, color: 'white', marginVertical: 7 }}>{group.members[1].name} owes you <Money value={14.2} color={C.amber} size={20} /></Text><Text style={{ fontSize: 10, color: '#D3DCE1' }}>Mostly last Tuesday’s taco run.</Text></View>}

    <SectionTitle right={<Pressable onPress={() => router.push('/shopping')}><Text style={{ fontSize: 11, color: C.navy, fontWeight: '700' }}>+ Add</Text></Pressable>}>Shared list</SectionTitle>
    <Text style={[styles.body, { paddingVertical: 12 }]}>No shared items yet.</Text>

    <SectionTitle>Split a receipt</SectionTitle>
    <Text style={[styles.body, { marginBottom: 10 }]}>Pick a recent receipt and we’ll help make it fair.</Text>
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 7, marginBottom: 12 }}>{receipts.slice(0, 5).map((item) => <Pressable key={item.id} onPress={() => { setReceiptId(item.id); setSplit(false); }} style={{ borderRadius: 11, padding: 9, backgroundColor: receiptId === item.id ? '#F5D768' : '#F1ECE2' }}><Text style={{ fontSize: 10, color: C.navy }}>{item.merchant} · {item.date}</Text></Pressable>)}</View>
    {receipt && <View style={[styles.panel, { marginBottom: 12 }]}><View style={[styles.row, { justifyContent: 'space-between', marginBottom: 8 }]}><View><Text style={{ fontSize: 13, fontWeight: '700', color: C.ink }}>{receipt.merchant}</Text><Text style={styles.tiny}>{receipt.date} · {receipt.items.length} items</Text></View><Money value={receipt.total} size={16} color={C.navy} /></View><Text style={[styles.tiny, { marginBottom: 10 }]} numberOfLines={2}>{receipt.items.slice(0, 4).map((item) => item.name).join(' · ')}</Text><View style={{ flexDirection: 'row', justifyContent: 'space-around', borderTopWidth: 1, borderColor: C.rule, paddingTop: 12 }}>{group.members.map((member, index) => <View key={member.name} style={{ alignItems: 'center', gap: 5 }}><View style={{ width: 25, height: 25, borderRadius: 14, backgroundColor: member.color, alignItems: 'center', justifyContent: 'center' }}><Text style={{ color: C.navy, fontWeight: '700', fontSize: 10 }}>{member.initial}</Text></View><Text style={{ fontSize: 9 }}>{index === 0 ? 'You' : member.name}</Text><Money value={split ? perPerson : 0} /></View>)}</View></View>}
    <Action kind="secondary" onPress={() => receipt ? setSplit(!split) : Alert.alert('Pick a receipt', 'Choose a receipt above before splitting it.')}>{split ? `✓ Split ${money(perPerson)} each` : 'Split evenly'}</Action>
    <Pressable onPress={leave} style={[styles.row, { justifyContent: 'center', gap: 7, minHeight: 46, marginTop: 12 }]}><LogOut size={15} color={C.tomato} /><Text style={{ fontSize: 11, color: C.tomato, fontWeight: '700' }}>Leave this group</Text></Pressable>
  </Screen>;
}

