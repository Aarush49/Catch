import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Alert, Image, Linking, Pressable, Text, View } from 'react-native';
import { router } from 'expo-router';
import { Check, ExternalLink, PiggyBank, Sparkles, X } from 'lucide-react-native';
import { Action, C, Eyebrow, Header, Money, Screen, money, styles } from '../components/tally';
import { moveToSavings } from '../services/bank';
import { carbonFactors } from '../services/receipts';
import { compareShoppingList, recordSwap, type ComparedItem, type ShoppingAlternative, type ShoppingComparison } from '../services/shopping';
import { useTally } from '../store/TallyProvider';

function AlternativeRow({ alt, selected, onPress }: { alt: ShoppingAlternative; selected: boolean; onPress: () => void }) {
  const open = () => Linking.openURL(alt.link).catch(() => Alert.alert('Could not open link', alt.link));
  return <Pressable accessibilityRole="radio" accessibilityState={{ selected }} onPress={onPress} style={{ flexDirection: 'row', gap: 10, alignItems: 'center', padding: 9, borderRadius: 13, borderWidth: 1.5, borderColor: selected ? C.jungle : 'transparent', backgroundColor: selected ? '#E3EFE0' : '#FFFAF1', marginTop: 8 }}>
    {alt.thumbnail ? <Image source={{ uri: alt.thumbnail }} style={{ width: 46, height: 46, borderRadius: 9, backgroundColor: '#EEE' }} resizeMode="contain" /> : <View style={{ width: 46, height: 46, borderRadius: 9, backgroundColor: '#E6E2D9' }} />}
    <View style={{ flex: 1, gap: 2 }}>
      <Text numberOfLines={2} style={{ fontSize: 11, fontWeight: '700', color: C.ink }}>{alt.title}</Text>
      <Text style={styles.tiny} numberOfLines={1}>{alt.source || 'Online store'}{alt.rating != null ? ` · ★ ${alt.rating}` : ''} · {alt.match_type === 'exact_title_match' ? 'Same name' : 'Similar item'}</Text>
      <Text style={{ fontSize: 10, fontWeight: '700', color: C.jungle }}>Save {money(alt.potential_savings)} ({alt.potential_savings_percent.toFixed(0)}%)</Text>
    </View>
    <View style={{ alignItems: 'flex-end', gap: 6 }}>
      <Money value={alt.price} color={C.jungle} />
      <Pressable accessibilityRole="link" accessibilityLabel={`Open ${alt.title}`} onPress={open} hitSlop={8} style={[styles.row, { gap: 3 }]}><Text style={{ fontSize: 10, color: C.navy, fontWeight: '700' }}>View</Text><ExternalLink size={11} color={C.navy} /></Pressable>
    </View>
  </Pressable>;
}

export default function Compare() {
  const { shopping, updateShoppingItem } = useTally();
  const [result, setResult] = useState<ShoppingComparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  // item_id -> index of the chosen alternative
  const [choices, setChoices] = useState<Record<string, number>>({});
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);
  const [savingsNote, setSavingsNote] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError(''); setChoices({}); setApplied(false); setSavingsNote('');
    try { setResult(await compareShoppingList()); }
    catch (err) { setResult(null); setError(err instanceof Error ? err.message : 'Price comparison failed. Please try again.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const selected = useMemo(() => (result?.items || []).flatMap((item) => {
    const index = choices[item.item_id];
    const alt = index === undefined ? undefined : item.alternatives[index];
    return alt ? [{ item, alt }] : [];
  }), [result, choices]);
  const saved = selected.reduce((sum, { alt }) => sum + alt.potential_savings, 0);
  const carbonLess = selected.reduce((sum, { item, alt }) => {
    const category = shopping.find((entry) => entry.id === item.item_id)?.category ?? 'Other';
    return sum + alt.potential_savings * carbonFactors[category];
  }, 0);

  const choose = (item: ComparedItem, index: number | null) => {
    if (applied) return;
    setChoices((current) => {
      const next = { ...current };
      if (index === null || next[item.item_id] === index) delete next[item.item_id];
      else next[item.item_id] = index;
      return next;
    });
  };

  const moveSwapSavings = async (done: { name: string; to: string; savings: number }[]) => {
    const amount = done.reduce((sum, swap) => sum + swap.savings, 0);
    const label = done.length === 1 ? `${done[0].name} → ${done[0].to}` : `${done.length} shopping list swaps`;
    setSavingsNote('Moving your savings into CATch savings…');
    try {
      const { moved, savingsTotal } = await moveToSavings(amount, label);
      const rounded = Math.abs(moved - amount) > 0.001 ? ' (the bank sandbox moves whole dollars)' : '';
      setSavingsNote(moved > 0
        ? `Moved ${money(moved)} into CATch savings${rounded}. Savings balance: ${money(savingsTotal)}.`
        : `${money(amount)} is under 50¢, so it stays in checking (the bank sandbox moves whole dollars).`);
    } catch (err) {
      setSavingsNote(err instanceof Error ? err.message : 'Could not move your savings. Please try again.');
    }
  };

  const apply = async () => {
    if (!selected.length || applying || applied) return;
    setApplying(true);
    const done: { name: string; to: string; savings: number }[] = [];
    try {
      for (const { item, alt } of selected) {
        const original = shopping.find((entry) => entry.id === item.item_id);
        if (!original) throw new Error(`"${item.name}" is no longer on your list.`);
        await updateShoppingItem(original.id, { name: alt.title, price: alt.price });
        try {
          await recordSwap({ originalName: original.name, replacementName: alt.title, savings: alt.potential_savings });
        } catch (err) {
          await updateShoppingItem(original.id, { name: original.name, price: original.price }).catch(() => {});
          throw err;
        }
        done.push({ name: original.name, to: alt.title, savings: alt.potential_savings });
      }
      setApplied(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Please try again.';
      Alert.alert('Could not apply every swap', done.length ? `Swapped: ${done.map((swap) => swap.name).join(', ')}.\n\n${message}` : message);
      if (done.length) setApplied(true);
    } finally { setApplying(false); }
    if (done.length) await moveSwapSavings(done);
  };

  if (loading) return <Screen><Header title="A few smart swaps" back="/shopping" /><View style={{ alignItems: 'center', paddingTop: 120, gap: 14 }}><ActivityIndicator color={C.navy} /><Text style={styles.h2}>Checking prices…</Text><Text style={[styles.body, { textAlign: 'center' }]}>Searching Google Shopping for cheaper options.{'\n'}This takes a few seconds per item.</Text></View></Screen>;

  if (error || !result) return <Screen><Header title="A few smart swaps" back="/shopping" /><View style={{ alignItems: 'center', paddingTop: 100, gap: 12 }}><X color={C.tomato} /><Text style={styles.h2}>Couldn’t compare prices</Text><Text style={[styles.body, { textAlign: 'center' }]}>{error}</Text><Action onPress={load} style={{ alignSelf: 'stretch' }}>Try again</Action></View></Screen>;

  return <Screen>
    <Header title="A few smart swaps" back="/shopping" />
    <Text style={[styles.body, { marginBottom: 14 }]}>Same good stuff. A little less spending.</Text>
    {result.items.length ? result.items.map((item) => <View key={item.item_id} style={{ backgroundColor: '#F6F1E8', borderWidth: 1, borderColor: '#DED8CB', borderRadius: 19, padding: 14, marginBottom: 12 }}>
      <View style={[styles.row, { gap: 9 }]}>
        <View style={{ height: 34, width: 34, borderRadius: 12, backgroundColor: '#F8D96C', alignItems: 'center', justifyContent: 'center' }}><Sparkles size={18} color="#72560C" /></View>
        <View style={{ flex: 1 }}><Text style={{ fontSize: 13, fontWeight: '700', color: C.ink }}>{item.name}</Text><Text style={styles.tiny}>{item.original_price == null ? 'No price yet' : `You usually pay ${money(item.original_price)}`}</Text></View>
        {choices[item.item_id] !== undefined && !applied && <Pressable onPress={() => choose(item, null)} style={{ backgroundColor: '#E6E2D9', paddingHorizontal: 10, paddingVertical: 7, borderRadius: 9 }}><Text style={{ fontSize: 10, color: '#57636A' }}>Keep mine</Text></Pressable>}
      </View>
      {item.error ? <Text style={{ fontSize: 11, color: C.tomato, marginTop: 10 }}>{item.error}</Text>
        : item.alternatives.length ? item.alternatives.map((alt, index) => <AlternativeRow key={`${alt.link}-${index}`} alt={alt} selected={choices[item.item_id] === index} onPress={() => choose(item, index)} />)
        : <Text style={[styles.tiny, { marginTop: 10 }]}>No cheaper listings found. Your price already looks good.</Text>}
    </View>) : <View style={{ alignItems: 'center', padding: 24 }}><Text style={styles.h2}>Nothing to compare</Text><Text style={[styles.body, { marginTop: 6, textAlign: 'center' }]}>Unchecked items with a price are compared. Add some on your shopping list.</Text></View>}
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', backgroundColor: '#D9EAD7', borderRadius: 17, padding: 14, marginTop: 4, marginBottom: 6 }}>
      <View><Eyebrow>{applied ? 'YOU SAVED' : 'YOU COULD SAVE'}</Eyebrow><Text style={{ fontFamily: 'Georgia', fontSize: 24, color: '#175B2C' }}>{money(saved)}</Text></View>
      <View style={{ alignItems: 'flex-end' }}><Eyebrow>CARBON LESS (EST.)</Eyebrow><Text style={{ fontFamily: 'Georgia', fontSize: 24, color: '#175B2C' }}>{carbonLess.toFixed(1)} kg</Text></View>
    </View>
    {result.total_potential_savings > 0 && <Text style={[styles.tiny, { marginBottom: 6 }]}>Up to {money(result.total_potential_savings)} if you pick the best option for every item.</Text>}
    <Text style={[styles.tiny, { marginBottom: 16 }]}>Savings compare listing prices only. Check size, quantity and seller; shipping and tax may be extra.</Text>
    {applied
      ? <Action onPress={() => router.replace('/shopping')}>✓ Swaps applied · Back to list</Action>
      : <Action onPress={apply} kind={selected.length ? 'primary' : 'secondary'}>{applying ? 'Applying…' : selected.length ? `Apply ${selected.length} swap${selected.length > 1 ? 's' : ''}  ✓` : 'Pick an option to swap'}</Action>}
    {!!savingsNote && <View style={[styles.row, { gap: 8, backgroundColor: '#E3EFE0', borderRadius: 14, padding: 12, marginTop: 12 }]}><PiggyBank size={17} color="#157536" /><Text style={{ flex: 1, fontSize: 11, lineHeight: 16, color: C.ink }}>{savingsNote}</Text></View>}
  </Screen>;
}
