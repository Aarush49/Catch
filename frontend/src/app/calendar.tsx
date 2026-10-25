import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { ChevronLeft, ChevronRight, Flame, ShoppingBag } from 'lucide-react-native';
import { Card, EmptyState, Header, Screen, SecondaryButton } from '../components/UI';
import { useAppStore } from '../store/AppStore';
import { colors, radius, typography } from '../theme';
import { calculateStreak, currency, receiptCarbon, receiptTotal } from '../lib/impact';

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export default function StreakCalendar() {
  const { receipts } = useAppStore();
  const [selectedDay, setSelectedDay] = useState(24);

  // October 2026 calendar calculations (Oct 1 is Thursday = index 4, 31 days)
  const startDayOffset = 4;
  const totalDays = 31;

  // Group receipts by October day number (e.g. "Oct 24" -> 24)
  const receiptsByDay = useMemo(() => {
    const map = new Map<number, typeof receipts>();
    receipts.forEach(r => {
      const match = r.date.match(/Oct\s*(\d+)/i);
      if (match) {
        const day = parseInt(match[1], 10);
        if (!map.has(day)) map.set(day, []);
        map.get(day)!.push(r);
      }
    });
    return map;
  }, [receipts]);

  // Dynamically compute the active streak using shared calculateStreak helper
  const { streakCount, streakDays } = useMemo(() => calculateStreak(receipts), [receipts]);

  // Receipts for currently highlighted day
  const activeReceipts = receiptsByDay.get(selectedDay) || [];
  const activeDayTotal = activeReceipts.reduce((s, r) => s + receiptTotal(r.items), 0);
  const activeDayCarbon = activeReceipts.reduce((s, r) => s + receiptCarbon(r.items), 0);

  // Calendar cells
  const calendarCells = useMemo(() => {
    const cells: (number | null)[] = [];
    for (let i = 0; i < startDayOffset; i++) {
      cells.push(null);
    }
    for (let d = 1; d <= totalDays; d++) {
      cells.push(d);
    }
    return cells;
  }, []);

  return (
    <Screen>
      <Header eyebrow="Activity & Habit" title="Streak Calendar" detail="October 2026" />

      {/* Streak Hero Card */}
      <View style={s.hero}>
        <View style={s.heroTop}>
          <View style={s.badge}>
            <Flame size={16} color={colors.tomato} />
            <Text style={s.badgeText}>{streakCount}-day streak active</Text>
          </View>
          <Text style={s.heroSub}>Keep logging receipts daily</Text>
        </View>
        <Text style={s.heroNumber}>{streakCount} {streakCount === 1 ? 'Day' : 'Days'}</Text>
        <Text style={s.heroBody}>
          {streakCount > 0
            ? `${streakCount} consecutive days of logging receipts! Consistent tracking powers accurate future projections and carbon insights.`
            : 'Log a receipt today to start your streak!'}
        </Text>
      </View>

      {/* Calendar Grid Card */}
      <Card>
        <View style={s.monthHeader}>
          <Text style={s.monthTitle}>October 2026</Text>
          <View style={s.monthNav}>
            <View style={s.navArrow}><ChevronLeft size={16} color={colors.muted} /></View>
            <View style={s.navArrow}><ChevronRight size={16} color={colors.muted} /></View>
          </View>
        </View>

        {/* Weekday headers */}
        <View style={s.weekdays}>
          {DAYS.map(day => (
            <Text key={day} style={s.weekdayText}>{day}</Text>
          ))}
        </View>

        {/* Day grid */}
        <View style={s.grid}>
          {calendarCells.map((day, idx) => {
            if (day === null) {
              return <View key={`empty-${idx}`} style={s.dayCell} />;
            }
            const dayReceipts = receiptsByDay.get(day);
            const hasPurchase = Boolean(dayReceipts && dayReceipts.length > 0);
            const isSelected = selectedDay === day;
            const isStreakDay = streakDays.has(day);

            return (
              <Pressable
                key={`day-${day}`}
                onPress={() => setSelectedDay(day)}
                style={[
                  s.dayCell,
                  hasPurchase && s.dayCellHasPurchase,
                  isStreakDay && s.dayCellStreak,
                  isSelected && s.dayCellSelected,
                ]}
              >
                <Text
                  style={[
                    s.dayText,
                    hasPurchase && s.dayTextHasPurchase,
                    isSelected && s.dayTextSelected,
                  ]}
                >
                  {day}
                </Text>
                {hasPurchase && (
                  <View style={[s.dot, isSelected && s.dotSelected]} />
                )}
              </Pressable>
            );
          })}
        </View>

        {/* Legend */}
        <View style={s.legend}>
          <View style={s.legendItem}>
            <View style={[s.legendColor, { backgroundColor: 'rgba(208,48,39,.18)', borderWidth: 1, borderColor: 'rgba(208,48,39,.4)' }]} />
            <Text style={s.legendText}>Active streak days</Text>
          </View>
          <View style={s.legendItem}>
            <View style={[s.legendColor, { backgroundColor: colors.regal }]} />
            <Text style={s.legendText}>Purchases logged</Text>
          </View>
        </View>
      </Card>

      {/* Schedule / Purchases by Selected Day */}
      <Card>
        <View style={s.scheduleHeader}>
          <View>
            <Text style={s.scheduleTitle}>October {selectedDay} Schedule</Text>
            <Text style={s.scheduleCaption}>
              {activeReceipts.length} {activeReceipts.length === 1 ? 'purchase' : 'purchases'} recorded
            </Text>
          </View>
          {activeReceipts.length > 0 && (
            <View style={{ alignItems: 'flex-end' }}>
              <Text style={s.scheduleTotal}>{currency(activeDayTotal, 2)}</Text>
              <Text style={s.scheduleCarbon}>est. {activeDayCarbon.toFixed(1)} kg CO2e</Text>
            </View>
          )}
        </View>

        {activeReceipts.length > 0 ? (
          <View style={s.timeline}>
            {activeReceipts.map((r, i) => (
              <Pressable
                key={r.id}
                onPress={() => router.push(`/receipt/${r.id}`)}
                style={[s.timelineItem, i === activeReceipts.length - 1 && { borderBottomWidth: 0 }]}
              >
                <View style={s.timeColumn}>
                  <Text style={s.timeText}>09:{30 + i * 25} AM</Text>
                  <View style={s.timeDot} />
                </View>
                <View style={s.receiptCard}>
                  <View style={s.receiptIcon}>
                    <ShoppingBag size={16} color={colors.regal} strokeWidth={1.75} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.merchantName}>{r.merchant}</Text>
                    <Text style={s.receiptItemsText}>
                      {r.items.map(it => it.name).join(', ')}
                    </Text>
                    <Text style={s.receiptMeta}>
                      {r.items.length} items · est. {receiptCarbon(r.items).toFixed(1)} kg CO2e
                    </Text>
                  </View>
                  <Text style={s.receiptPrice}>{currency(receiptTotal(r.items), 2)}</Text>
                </View>
              </Pressable>
            ))}
          </View>
        ) : (
          <EmptyState
            title={`No purchases on Oct ${selectedDay}`}
            detail="Select another day or tap a highlighted date to inspect your scheduled purchases."
          />
        )}
      </Card>

      <SecondaryButton label="Back to home" onPress={() => router.back()} />
    </Screen>
  );
}

const s = StyleSheet.create({
  hero: {
    backgroundColor: colors.prussian,
    borderRadius: radius.card,
    padding: 20,
  },
  heroTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(234,228,217,.12)',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 99,
  },
  badgeText: {
    fontFamily: typography.medium,
    fontSize: 12,
    color: colors.linen,
  },
  heroSub: {
    fontFamily: typography.regular,
    fontSize: 12,
    color: 'rgba(234,228,217,.65)',
  },
  heroNumber: {
    fontSize: 40,
    color: colors.linen,
    fontFamily: typography.semibold,
    letterSpacing: -1.5,
  },
  heroBody: {
    fontFamily: typography.regular,
    fontSize: 13,
    color: 'rgba(234,228,217,.7)',
    marginTop: 6,
    lineHeight: 18,
  },
  monthHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  monthTitle: {
    fontFamily: typography.semibold,
    fontSize: 18,
    color: colors.ink,
  },
  monthNav: {
    flexDirection: 'row',
    gap: 8,
  },
  navArrow: {
    width: 28,
    height: 28,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  weekdays: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  weekdayText: {
    width: '14.28%',
    textAlign: 'center',
    fontFamily: typography.medium,
    fontSize: 11,
    color: colors.muted,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  dayCell: {
    width: '14.28%',
    height: 42,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 10,
    marginVertical: 2,
    position: 'relative',
  },
  dayCellHasPurchase: {
    backgroundColor: 'rgba(0,58,112,.06)',
  },
  dayCellStreak: {
    borderWidth: 1,
    borderColor: 'rgba(208,48,39,.35)',
    backgroundColor: 'rgba(208,48,39,.08)',
  },
  dayCellSelected: {
    backgroundColor: colors.regal,
    borderColor: colors.regal,
  },
  dayText: {
    fontFamily: typography.medium,
    fontSize: 13,
    color: colors.ink,
  },
  dayTextHasPurchase: {
    fontFamily: typography.semibold,
    color: colors.regal,
  },
  dayTextSelected: {
    color: colors.linen,
  },
  dot: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.regal,
    marginTop: 2,
  },
  dotSelected: {
    backgroundColor: colors.linen,
  },
  legend: {
    flexDirection: 'row',
    gap: 16,
    marginTop: 14,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  legendColor: {
    width: 10,
    height: 10,
    borderRadius: 3,
  },
  legendText: {
    fontFamily: typography.regular,
    fontSize: 11,
    color: colors.muted,
  },
  scheduleHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
  },
  scheduleTitle: {
    fontFamily: typography.semibold,
    fontSize: 18,
    color: colors.ink,
  },
  scheduleCaption: {
    fontFamily: typography.regular,
    fontSize: 12,
    color: colors.muted,
    marginTop: 2,
  },
  scheduleTotal: {
    fontFamily: typography.semibold,
    fontSize: 20,
    color: colors.ink,
    fontVariant: ['tabular-nums'],
  },
  scheduleCarbon: {
    fontFamily: typography.regular,
    fontSize: 11,
    color: colors.jungle,
    marginTop: 2,
  },
  timeline: {
    gap: 12,
  },
  timelineItem: {
    flexDirection: 'row',
    gap: 12,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  timeColumn: {
    width: 65,
    alignItems: 'flex-start',
    paddingTop: 2,
  },
  timeText: {
    fontFamily: typography.medium,
    fontSize: 11,
    color: colors.muted,
  },
  timeDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.amber,
    marginTop: 6,
  },
  receiptCard: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
  },
  receiptIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.linen,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
  },
  merchantName: {
    fontFamily: typography.semibold,
    fontSize: 14,
    color: colors.ink,
  },
  receiptItemsText: {
    fontFamily: typography.regular,
    fontSize: 12,
    color: colors.prussian,
    marginTop: 2,
  },
  receiptMeta: {
    fontFamily: typography.regular,
    fontSize: 11,
    color: colors.muted,
    marginTop: 3,
  },
  receiptPrice: {
    fontFamily: typography.semibold,
    fontSize: 14,
    color: colors.ink,
    fontVariant: ['tabular-nums'],
  },
});
