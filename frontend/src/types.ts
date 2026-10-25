export type Category='dining'|'grocery'|'transport'|'shopping'|'entertainment'|'utilities'|'other';
export type ReceiptItem={id:string;name:string;price:number;category:Category};
export type Receipt={id:string;merchant:string;date:string;items:ReceiptItem[]};
export type ShoppingItem={id:string;name:string;checked:boolean;cheaperElsewhere?:boolean};
export type Recommendation={id:string;itemName:string;alternative:string;store:string;originalPrice:number;newPrice:number;originalCarbon:number;newCarbon:number;accepted:boolean};
