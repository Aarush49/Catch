import { Recommendation, Receipt, ShoppingItem } from '../types';
export const seedReceipts:Receipt[]=[
 {id:'r4',merchant:'Sunrise Coffee',date:'Oct 24',items:[{id:'i6',name:'Coffee',price:6.8,category:'dining'}]},
 {id:'r1',merchant:'H-E-B Market',date:'Oct 23',items:[{id:'i1',name:'Oat milk',price:4.79,category:'grocery'},{id:'i2',name:'Coffee beans',price:12.49,category:'grocery'},{id:'i3',name:'Produce',price:51.14,category:'grocery'}]},
 {id:'r3',merchant:'Ride Austin',date:'Oct 22',items:[{id:'i5',name:'Rideshare',price:18.75,category:'transport'}]},
 {id:'r8',merchant:'Wheatsville Co-op',date:'Oct 21',items:[{id:'i10',name:'Kombucha & Snack',price:8.45,category:'grocery'}]},
 {id:'r2',merchant:'Trail Supply',date:'Oct 20',items:[{id:'i4',name:'Day pack',price:84,category:'shopping'}]},
 {id:'r9',merchant:'Barton Springs Bakery',date:'Oct 19',items:[{id:'i11',name:'Pastry & Tea',price:7.25,category:'dining'}]},
 {id:'r6',merchant:'Alamo Cinema',date:'Oct 18',items:[{id:'i8',name:'Movie ticket',price:31.5,category:'entertainment'}]},
 {id:'r7',merchant:'Green Bowl',date:'Oct 16',items:[{id:'i9',name:'Lunch',price:14.2,category:'dining'}]},
 {id:'r5',merchant:'Austin Energy',date:'Oct 14',items:[{id:'i7',name:'Electric service',price:92.1,category:'utilities'}]},
];
export const seedShopping:ShoppingItem[]=[{id:'s1',name:'Oat milk',checked:false,cheaperElsewhere:true},{id:'s2',name:'Dish soap refill',checked:false,cheaperElsewhere:true},{id:'s3',name:'Bus passes',checked:true}];
export const mockParsedItems=seedReceipts[0].items.map(x=>({...x,id:`draft-${x.id}`}));
export const mockRecommendations:Recommendation[]=[{id:'rec1',itemName:'Oat milk',alternative:'Store-brand oat milk',store:'H-E-B',originalPrice:4.79,newPrice:3.49,originalCarbon:.7,newCarbon:.5,accepted:false},{id:'rec2',itemName:'Dish soap refill',alternative:'Bulk refill',store:'Wheatsville',originalPrice:8.99,newPrice:6.5,originalCarbon:1.1,newCarbon:.6,accepted:false}];
export const parseReceipt=async()=>{await new Promise(r=>setTimeout(r,900));return mockParsedItems.map(x=>({...x}));};
export const compareShoppingList=async()=>{await new Promise(r=>setTimeout(r,500));return mockRecommendations.map(x=>({...x}));};
