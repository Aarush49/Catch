import { estimateCarbon, futureValue } from "../lib/impact.js";
const raw = [
  ["p1","Oct 24","Sunrise Coffee",6.8,"dining","Coffee"],["p2","Oct 23","H-E-B Market",68.42,"grocery","Groceries"],
  ["p3","Oct 22","Ride Austin",18.75,"transport","Rideshare"],["p4","Oct 20","Trail Supply",84,"shopping","Shopping"],
  ["p5","Oct 18","Alamo Cinema",31.5,"entertainment","Movies"],["p6","Oct 16","Green Bowl",14.2,"dining","Lunch"],
  ["p7","Oct 14","Austin Energy",92.1,"utilities","Utilities"],
];
export const purchases = raw.map(([id,date,merchant,amount,category,label]) => ({ id,date,merchant,amount,category,label,carbon:+estimateCarbon(amount,category).toFixed(1),future:+futureValue(amount).toFixed(0) }));
export const spendingByDay = Array.from({ length:30 },(_,i)=>({ day:i+1,amount:[0,12,24,8,46,18,0,72,14,31][i%10]+((i*7)%11) }));
export const alternatives = { p1:[{name:"Brew at home",note:"Reusable filter",savings:5.4,carbon:.2},{name:"Local drip coffee",note:"Bring your own mug",savings:2.3,carbon:.5},{name:"Office coffee",note:"Already brewed",savings:6.8,carbon:.1}], default:[{name:"Buy refurbished",note:"Same utility, longer life",savings:24,carbon:3.2},{name:"Choose local",note:"Lower delivery footprint",savings:12,carbon:4.1},{name:"Wait 48 hours",note:"Skip the impulse",savings:31,carbon:0}] };
export const household = [{id:"m1",name:"You",initials:"YO",color:"bg-regal"},{id:"m2",name:"Maya",initials:"MA",color:"bg-jungle"},{id:"m3",name:"Leo",initials:"LE",color:"bg-amber text-ink"}];
export const sharedList = ["Oat milk","Dish soap refill","Bus passes"];
export const receiptItems = [{name:"Oat milk",amount:4.79,carbon:.7},{name:"Coffee beans",amount:12.49,carbon:1.4},{name:"Avocados",amount:5.2,carbon:.9}];
