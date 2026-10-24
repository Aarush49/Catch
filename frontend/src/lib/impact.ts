import { Category } from '../types';
export const factors:Record<Category,number>={dining:.18,grocery:.09,transport:.24,shopping:.14,entertainment:.08,utilities:.32,other:.12};
export const estimateCarbon=(amount:number,category:Category='other')=>amount*(factors[category]??factors.other);
export const futureValue=(amount:number,years=30,rate=.07)=>amount*(1+rate)**years;
export const buildTimeline=(original:number,changed:number,years=30)=>Array.from({length:years+1},(_,year)=>({year,original:futureValue(original,year),changed:futureValue(changed,year)}));
export const receiptTotal=(items:{price:number}[])=>items.reduce((sum,item)=>sum+Number(item.price||0),0);
export const receiptCarbon=(items:{price:number;category:Category}[])=>items.reduce((sum,item)=>sum+estimateCarbon(item.price,item.category),0);
export const currency=(value:number,digits=0)=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:digits}).format(value);
