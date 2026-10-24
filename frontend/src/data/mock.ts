export type Category = 'Groceries' | 'Dining' | 'Household' | 'Health' | 'Transport' | 'Other';
export type LineItem = { id: string; name: string; quantity: number; price: number; category: Category; carbon: number; confidence?: boolean };
export type Receipt = { id: string; merchant: string; date: string; total: number; tax: number; items: LineItem[] };
const items = [
  ['Ground beef', 7.49, 'Groceries', 6.2], ['Avocados (3 ct)', 4.29, 'Groceries', .7], ['Sourdough loaf', 5.5, 'Groceries', .8], ['Oat milk', 4.19, 'Groceries', .4], ['Organic eggs', 6.99, 'Groceries', 1.1], ['Baby spinach', 3.49, 'Groceries', .2], ['Chicken thighs', 8.79, 'Groceries', 3.8], ['Greek yogurt', 5.29, 'Groceries', .9], ['Heirloom tomatoes', 4.99, 'Groceries', .4], ['Pasta shells', 2.19, 'Groceries', .3], ['Olive oil', 11.99, 'Groceries', 1.4], ['Cheddar cheese', 5.49, 'Groceries', 2.1], ['Almonds', 7.99, 'Groceries', .9], ['Blueberries', 5.99, 'Groceries', .3], ['Dish soap', 4.49, 'Household', .8], ['Paper towels', 8.99, 'Household', 1.7], ['Sparkling water', 4.99, 'Groceries', .5], ['Cold brew', 5.49, 'Dining', .7], ['Ibuprofen', 6.29, 'Health', .5], ['Gas', 36.18, 'Transport', 5.8], ['Taco Tuesday', 18.5, 'Dining', 2.3], ['Toothpaste', 4.79, 'Health', .4], ['Laundry detergent', 12.47, 'Household', 2.4], ['Dark chocolate', 4.29, 'Groceries', .6], ['Bananas', 2.18, 'Groceries', .2], ['Canned chickpeas', 1.49, 'Groceries', .2], ['Coffee beans', 13.99, 'Groceries', 1.2], ['Cilantro bunch', .99, 'Groceries', .1], ['Salmon fillet', 14.85, 'Groceries', 4.2], ['Rice (2 lb)', 4.79, 'Groceries', .6]] as const;
const merchants = ['H-E-B', "Trader Joe's", 'Whole Foods', 'Target', 'Walgreens'];
export const mockReceipts: Receipt[] = Array.from({ length: 25 }, (_, n) => {
  const day = new Date(2026, 9, 23 - n * 1.6);
  const count = 4 + (n % 5);
  const chosen = Array.from({ length: count }, (_, i) => items[(n * 3 + i * 5) % items.length]);
  const lineItems = chosen.map((it, i) => ({ id: `${n}-${i}`, name: it[0], quantity: 1, price: it[1], category: it[2] as Category, carbon: it[3], ...(i === count - 1 && n % 3 === 0 ? { confidence: true } : {}) }));
  const subtotal = lineItems.reduce((s, it) => s + it.price, 0); const tax = +(subtotal * .0825).toFixed(2);
  return { id: `receipt-${n}`, merchant: merchants[n % merchants.length], date: day.toISOString().slice(0, 10), total: +(subtotal + tax).toFixed(2), tax, items: lineItems };
});
export const categories: Category[] = ['Groceries', 'Dining', 'Household', 'Health', 'Transport', 'Other'];
export const alternatives: Record<string, {name:string;store:string;price:number;carbon:number}> = {
  'Ground beef': { name: 'Lentil crumbles', store: "Trader Joe's", price: 4.99, carbon: 1.1 },
  'Oat milk': { name: 'Oat beverage', store: 'H-E-B', price: 3.19, carbon: .3 },
  'Paper towels': { name: 'Reusable cloths', store: 'Target', price: 6.49, carbon: .8 },
  'Greek yogurt': { name: 'Plain yogurt', store: 'H-E-B', price: 3.99, carbon: .7 },
  'Avocados (3 ct)': { name: 'Avocados (3 ct)', store: 'H-E-B', price: 3.49, carbon: .6 },
};
