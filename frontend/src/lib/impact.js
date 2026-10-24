const factors = { dining: .18, grocery: .09, transport: .24, shopping: .14, entertainment: .08, utilities: .32, other: .12 };
export const futureValue = (amount, years = 30, rate = .07) => amount * (1 + rate) ** years;
export const estimateCarbon = (amount, category = "other") => amount * (factors[category] ?? factors.other);
export const currency = (value, digits = 0) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: digits }).format(value);
export const buildTimeline = (original, changed, years = 30) => Array.from({ length: years + 1 }, (_, year) => ({ year, original: +futureValue(original, year).toFixed(2), changed: +futureValue(changed, year).toFixed(2) }));
