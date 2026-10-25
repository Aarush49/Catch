import React, { useMemo, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { router } from 'expo-router';
import { CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react-native';
import { C, Empty, Header, money, ReceiptRow, Screen, styles } from '../components/tally';
import { useTally } from '../store/TallyProvider';

const weekDays = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
const dateKey = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;

export default function PurchaseCalendar() {
  const { receipts } = useTally();
  const newest = [...receipts].sort((a, b) => b.date.localeCompare(a.date))[0]?.date;
  const initialDate = newest ? new Date(`${newest}T12:00:00`) : new Date();
  const [month, setMonth] = useState(new Date(initialDate.getFullYear(), initialDate.getMonth(), 1));
  const [selected, setSelected] = useState(newest ?? dateKey(initialDate));

  const receiptsByDate = useMemo(() => receipts.reduce<Record<string, typeof receipts>>((groups, receipt) => {
    (groups[receipt.date] ??= []).push(receipt);
    return groups;
  }, {}), [receipts]);

  const leading = month.getDay();
  const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const cells = Array.from({ length: Math.ceil((leading + daysInMonth) / 7) * 7 }, (_, index) => {
    const day = index - leading + 1;
    return day > 0 && day <= daysInMonth ? day : null;
  });
  const selectedReceipts = receiptsByDate[selected] ?? [];
  const selectedDate = new Date(`${selected}T12:00:00`);
  const monthLabel = month.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

  const moveMonth = (offset: number) => {
    const next = new Date(month.getFullYear(), month.getMonth() + offset, 1);
    setMonth(next);
    setSelected(dateKey(next));
  };

  return (
    <Screen>
      <Header title="Purchase calendar" />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 4 }}>
        <View style={{ width: 42, height: 42, borderRadius: 14, backgroundColor: '#F5CE58', alignItems: 'center', justifyContent: 'center' }}>
          <CalendarDays size={21} color={C.navy} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.h2}>Your purchase schedule</Text>
          <Text style={styles.tiny}>Tap a day to see what you bought.</Text>
        </View>
      </View>

      <View style={[styles.panel, { padding: 12 }]}>
        <View style={[styles.row, { justifyContent: 'space-between', marginBottom: 15 }]}>
          <Pressable accessibilityLabel="Previous month" onPress={() => moveMonth(-1)} style={{ width: 34, height: 34, borderRadius: 11, backgroundColor: '#E2DDD3', alignItems: 'center', justifyContent: 'center' }}><ChevronLeft size={17} color={C.navy} /></Pressable>
          <Text style={{ fontFamily: 'Georgia', fontSize: 18, color: C.navy, fontWeight: '600' }}>{monthLabel}</Text>
          <Pressable accessibilityLabel="Next month" onPress={() => moveMonth(1)} style={{ width: 34, height: 34, borderRadius: 11, backgroundColor: '#E2DDD3', alignItems: 'center', justifyContent: 'center' }}><ChevronRight size={17} color={C.navy} /></Pressable>
        </View>

        <View style={{ flexDirection: 'row' }}>
          {weekDays.map((day) => <Text key={day} style={{ width: `${100 / 7}%`, textAlign: 'center', fontSize: 8, letterSpacing: 1, fontWeight: '700', color: C.muted, marginBottom: 8 }}>{day}</Text>)}
        </View>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap' }}>
          {cells.map((day, index) => {
            if (!day) return <View key={`blank-${index}`} style={{ width: `${100 / 7}%`, height: 48 }} />;
            const key = dateKey(new Date(month.getFullYear(), month.getMonth(), day));
            const purchases = receiptsByDate[key] ?? [];
            const active = selected === key;
            return (
              <Pressable key={key} onPress={() => setSelected(key)} style={{ width: `${100 / 7}%`, height: 48, alignItems: 'center', justifyContent: 'center' }}>
                <View style={{ width: 34, height: 34, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: active ? C.navy : 'transparent' }}>
                  <Text style={{ fontSize: 12, fontWeight: purchases.length ? '700' : '400', color: active ? '#FFFFFF' : C.ink }}>{day}</Text>
                  {purchases.length > 0 && <View style={{ position: 'absolute', bottom: 3, width: 4, height: 4, borderRadius: 4, backgroundColor: active ? C.amber : C.tomato }} />}
                </View>
              </Pressable>
            );
          })}
        </View>
      </View>

      <View style={[styles.row, { justifyContent: 'space-between', marginTop: 6 }]}>
        <View>
          <Text style={styles.h2}>{selectedDate.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</Text>
          <Text style={styles.tiny}>{selectedReceipts.length ? `${selectedReceipts.length} purchase${selectedReceipts.length === 1 ? '' : 's'} scheduled` : 'No purchases recorded'}</Text>
        </View>
        {selectedReceipts.length > 0 && <Text style={{ fontSize: 14, color: C.navy, fontWeight: '700' }}>{money(selectedReceipts.reduce((sum, receipt) => sum + receipt.total, 0))}</Text>}
      </View>

      {selectedReceipts.length ? selectedReceipts.map((receipt) => (
        <ReceiptRow key={receipt.id} merchant={receipt.merchant} date={receipt.date} total={receipt.total} carbon={receipt.items.reduce((sum, item) => sum + item.carbon, 0)} onPress={() => router.push({ pathname: '/receipt/[id]', params: { id: receipt.id } })} />
      )) : <Empty title="A quiet day" copy="There are no purchases saved for this date." />}
    </Screen>
  );
}
