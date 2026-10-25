import React, { useRef, useState } from 'react';
import { Alert, Pressable, Text, TextInput, View } from 'react-native';
import { router } from 'expo-router';
import { Check, Plus, Sparkles, X } from 'lucide-react-native';
import { Action, C, Header, Screen, dateLabel, money, styles } from '../components/tally';
import { lastPurchase, type ShoppingItem } from '../services/shopping';
import { useTally } from '../store/TallyProvider';

const parsePrice = (text: string) => {
  const cleaned = text.replace(/[$,\s]/g, '');
  if (!cleaned) return null;
  const value = Number(cleaned);
  return Number.isFinite(value) && value > 0 ? +value.toFixed(2) : NaN;
};
const failed = (title: string, error: unknown) => Alert.alert(title, error instanceof Error ? error.message : 'Please try again.');

function PriceField({ item, onSave }: { item: ShoppingItem; onSave: (price: number | null) => Promise<void> }) {
  const [text, setText] = useState<string | null>(null);
  // End-editing and blur both fire; the ref makes the second call a no-op.
  const edited = useRef<string | null>(null);
  const shown = text ?? (item.price == null ? '' : item.price.toFixed(2));
  const change = (value: string) => { edited.current = value; setText(value); };
  const commit = async () => {
    const value = edited.current;
    if (value === null) return;
    edited.current = null;
    const price = parsePrice(value);
    setText(null);
    if (Number.isNaN(price)) { Alert.alert('Check the price', 'Enter an amount above $0, like 4.19.'); return; }
    if (price === item.price) return;
    await onSave(price);
  };
  return <View style={[styles.row, { borderBottomWidth: 1, borderColor: item.price == null ? C.tomato : '#C5C7BD', paddingHorizontal: 2 }]}>
    <Text style={{ fontSize: 11, color: '#485662' }}>$</Text>
    <TextInput accessibilityLabel={`Usual price for ${item.name}`} value={shown} onChangeText={change} onEndEditing={commit} onBlur={commit} onSubmitEditing={commit} placeholder="price" placeholderTextColor={C.tomato} keyboardType="decimal-pad" returnKeyType="done" style={{ width: 52, fontSize: 11, color: '#485662', paddingVertical: 4 }} />
  </View>;
}

export default function Shopping() {
  const { shopping, receipts, addShoppingItem, updateShoppingItem, removeShoppingItem } = useTally();
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState<string | null>(null);
  const [pendingPrice, setPendingPrice] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const toCompare = shopping.filter((item) => !item.completed);

  const add = async () => {
    const name = draft.trim();
    if (!name || busy) return;
    const match = lastPurchase(receipts, name);
    if (!match) { setPending(name); setPendingPrice(''); setNote(''); return; }
    setBusy(true);
    try {
      await addShoppingItem({ name, price: match.price, category: match.category });
      setDraft(''); setNote(`${money(match.price)} from your ${match.merchant} receipt (${dateLabel(match.date)}).`);
    } catch (error) { failed('Could not add item', error); } finally { setBusy(false); }
  };
  const addPending = async (withPrice: boolean) => {
    if (!pending || busy) return;
    const price = withPrice ? parsePrice(pendingPrice) : null;
    if (withPrice && (price === null || Number.isNaN(price))) { Alert.alert('Check the price', 'Enter an amount above $0, like 4.19, or tap Skip.'); return; }
    setBusy(true);
    try {
      await addShoppingItem({ name: pending, price, category: 'Other' });
      setDraft(''); setPending(null); setNote(price == null ? 'Added without a price; add one to compare it.' : '');
    } catch (error) { failed('Could not add item', error); } finally { setBusy(false); }
  };
  const update = (id: string, patch: Partial<Pick<ShoppingItem, 'price' | 'completed'>>) => updateShoppingItem(id, patch).then(() => undefined, (error) => failed('Could not update item', error));
  const remove = (id: string) => removeShoppingItem(id).catch((error) => failed('Could not remove item', error));

  return <Screen>
    <Header title="Shopping list" back="/" />
    <Text style={[styles.body, { marginBottom: 18 }]}>A little plan goes a long way.</Text>
    <View style={{ height: 52, borderWidth: 1, borderColor: '#C5C7BD', backgroundColor: '#F7F3EB', borderRadius: 15, flexDirection: 'row', padding: 4, paddingLeft: 13, alignItems: 'center', marginBottom: pending || note ? 8 : 16 }}>
      <TextInput placeholder="Add something to your list" placeholderTextColor="#88918D" value={draft} onChangeText={(value) => { setDraft(value); setPending(null); setNote(''); }} onSubmitEditing={add} returnKeyType="done" editable={!busy} style={{ flex: 1, fontSize: 12, color: C.ink }} />
      <Pressable accessibilityRole="button" accessibilityLabel="Add item" onPress={add} style={{ height: 42, width: 42, borderRadius: 12, backgroundColor: busy ? '#7B8B9E' : C.navy, alignItems: 'center', justifyContent: 'center' }}><Plus color="white" /></Pressable>
    </View>
    {pending ? <View style={[styles.panel, { marginBottom: 16, gap: 10 }]}>
      <Text style={{ fontSize: 12, color: C.ink }}>What do you usually pay for <Text style={{ fontWeight: '700' }}>{pending}</Text>?</Text>
      <View style={[styles.row, { gap: 8 }]}>
        <View style={[styles.row, { flex: 1, borderBottomWidth: 1, borderColor: '#B7BDB5' }]}><Text style={{ color: C.navy }}>$</Text><TextInput autoFocus value={pendingPrice} onChangeText={setPendingPrice} onSubmitEditing={() => addPending(true)} keyboardType="decimal-pad" placeholder="4.19" placeholderTextColor="#88918D" style={{ flex: 1, minHeight: 40, fontSize: 13, color: C.ink, paddingHorizontal: 4 }} /></View>
        <Pressable onPress={() => addPending(true)} style={{ backgroundColor: C.navy, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 10 }}><Text style={{ color: 'white', fontSize: 11, fontWeight: '700' }}>Add</Text></Pressable>
        <Pressable onPress={() => addPending(false)} style={{ backgroundColor: '#E6E2D9', paddingHorizontal: 12, paddingVertical: 10, borderRadius: 10 }}><Text style={{ color: '#57636A', fontSize: 11 }}>Skip</Text></Pressable>
      </View>
    </View> : note ? <Text style={[styles.tiny, { marginBottom: 14 }]}>{note}</Text> : null}
    {shopping.map((item) => <View key={item.id} style={[styles.row, styles.divider, { minHeight: 60, gap: 10 }]}>
      <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: item.completed }} onPress={() => update(item.id, { completed: !item.completed })} style={{ height: 23, width: 23, borderRadius: 7, borderWidth: 1.5, borderColor: item.completed ? C.jungle : '#9BA6A0', backgroundColor: item.completed ? C.jungle : 'transparent', alignItems: 'center', justifyContent: 'center' }}>{item.completed && <Check size={14} color="white" />}</Pressable>
      <View style={{ flex: 1, gap: 3 }}>
        <Text style={{ fontSize: 12, fontWeight: '700', color: item.completed ? '#87908A' : C.ink, textDecorationLine: item.completed ? 'line-through' : 'none' }}>{item.name}</Text>
        <Text style={styles.tiny}>{item.category}{item.price == null ? ' · add a price to compare' : ''}</Text>
      </View>
      <PriceField item={item} onSave={(price) => update(item.id, { price })} />
      <Pressable accessibilityRole="button" accessibilityLabel={`Remove ${item.name}`} onPress={() => remove(item.id)} hitSlop={10}><X size={15} color="#A5A8A1" /></Pressable>
    </View>)}
    {shopping.length === 0 && <View style={{ padding: 24, alignItems: 'center' }}><Text style={styles.h2}>Nothing on the list</Text><Text style={[styles.body, { marginTop: 6 }]}>Add a few things you need this week.</Text></View>}
    <View style={[styles.row, { gap: 7, backgroundColor: '#E5EADF', padding: 12, borderRadius: 14, marginTop: 18 }]}><Sparkles size={16} color="#4D7B3D" /><Text style={{ flex: 1, fontSize: 10, color: '#6C7771' }}>We search Google Shopping for cheaper options on unchecked items that have a price.</Text></View>
    <Action onPress={() => toCompare.length ? router.push('/compare') : router.replace('/home')} style={{ marginTop: 18 }}>{toCompare.length ? 'Done shopping  →' : 'Back to Home'}</Action>
  </Screen>;
}
