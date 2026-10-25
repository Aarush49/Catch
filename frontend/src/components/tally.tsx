import React, { useCallback, useEffect, useRef } from 'react';
import { Animated, DeviceEventEmitter, Dimensions, Easing, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Circle, Line, Path, Rect, Text as SvgText } from 'react-native-svg';
import { ArrowLeft, BarChart3, Camera, ChevronRight, Home, ReceiptText, TrendingDown, Users, Sparkles, UserRound } from 'lucide-react-native';
import { router, useFocusEffect, usePathname } from 'expo-router';
import type { Category } from '../data/mock';
import { backOrHome, useTransitions } from '../store/TransitionProvider';

const AnimatedPath = Animated.createAnimatedComponent(Path);

export const C={linen:'#EAE4D9',navy:'#003A70',tomato:'#D03027',jungle:'#16A34A',amber:'#FBBF24',ink:'#081627',prussian:'#11233B',muted:'#75817F',rule:'rgba(8,22,39,.13)'};
export const money=(v:number)=>'$'+v.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
export const dateLabel=(v:string)=>new Date(`${v}T12:00:00`).toLocaleDateString('en-US',{month:'short',day:'numeric'});
export const styles=StyleSheet.create({screen:{flex:1,backgroundColor:C.linen},content:{paddingHorizontal:20,paddingTop:8,paddingBottom:134},h1:{fontFamily:'Georgia',fontSize:37,lineHeight:41,color:C.navy,fontWeight:'600'},h2:{fontFamily:'Georgia',fontSize:22,color:C.navy,fontWeight:'600'},eyebrow:{fontSize:9,letterSpacing:1.5,fontWeight:'700',color:'#65727C',marginBottom:7},body:{fontSize:12,color:'#6C777C'},row:{flexDirection:'row',alignItems:'center'},divider:{borderBottomWidth:StyleSheet.hairlineWidth,borderColor:C.rule},panel:{backgroundColor:'#F3EEE5',borderRadius:20,padding:15},titleRow:{flexDirection:'row',alignItems:'center',justifyContent:'space-between',marginTop:18,marginBottom:8},btn:{minHeight:48,borderRadius:15,backgroundColor:C.navy,borderBottomWidth:4,borderBottomColor:'#002B53',alignItems:'center',justifyContent:'center',flexDirection:'row',gap:8,paddingHorizontal:15},btnText:{fontSize:13,color:'#fff',fontWeight:'700'},secondary:{backgroundColor:'#DCE4E8',borderBottomColor:'#B8C5CE'},secondaryText:{color:C.navy},textInput:{minHeight:44,borderBottomWidth:1,borderColor:'#B7BDB5',fontSize:13,color:C.ink,paddingHorizontal:2},tiny:{fontSize:10,color:C.muted}});

export function Money({value,size=13,color=C.ink}:{value:number;size?:number;color?:string}){return <Text style={{fontSize:size,color,fontVariant:['tabular-nums'] as never,fontWeight:'600'}}>{money(value)}</Text>}
export function Eyebrow({children}:{children:React.ReactNode}){return <Text style={styles.eyebrow}>{children}</Text>}
export function Action({children,onPress,kind='primary',style}:{children:React.ReactNode;onPress:()=>void;kind?:'primary'|'secondary'|'ghost'|'danger';style?:object}){const secondary=kind==='secondary';return <Pressable onPress={onPress} style={({pressed})=>[styles.btn,secondary&&styles.secondary,kind==='danger'&&{backgroundColor:'#F3D5D0',borderBottomColor:'#E7B9B2'},kind==='ghost'&&{backgroundColor:'transparent',borderBottomWidth:0},style,pressed&&{transform:[{translateY:2}],borderBottomWidth:1}]}><Text style={[styles.btnText,secondary&&styles.secondaryText,kind==='danger'&&{color:C.tomato},kind==='ghost'&&{color:C.navy}]}>{children}</Text></Pressable>}
export function MorphPressable({children,route,style,accessibilityLabel}:{children:React.ReactNode;route:string;style?:any;accessibilityLabel?:string}){const ref=useRef<View>(null);const transitions=useTransitions();return <Pressable ref={ref} accessibilityRole="button" accessibilityLabel={accessibilityLabel} onPress={()=>ref.current?.measureInWindow((x,y,width,height)=>transitions.morphTo(route,{x,y,width,height}))} style={style}>{children}</Pressable>}
export function Screen({children,scroll=true,dark=false,popDelay=0}:{children:React.ReactNode;scroll?:boolean;dark?:boolean;popDelay?:number}){const insets=useSafeAreaInsets();const transitions=useTransitions();const offset=useRef(new Animated.Value(0)).current;useFocusEffect(useCallback(()=>transitions.registerBack((route,done)=>{offset.setValue(0);Animated.timing(offset,{toValue:-Dimensions.get('window').width,duration:440,easing:Easing.inOut(Easing.cubic),useNativeDriver:true}).start(()=>{if(route)router.replace(route as never);else backOrHome();done?.();});}),[transitions.registerBack]));const animatedChildren=React.Children.toArray(children).map((child,index)=>{const childKey=React.isValidElement(child)&&child.key?String(child.key):String(index);return <PopIn key={`${index}-${childKey}`} delay={popDelay+index*42}>{child}</PopIn>});return <Animated.View style={[styles.screen,dark&&{backgroundColor:C.prussian},{transform:[{translateX:offset}]}]}><ScrollView showsVerticalScrollIndicator={false} showsHorizontalScrollIndicator={false} keyboardShouldPersistTaps="handled" contentContainerStyle={[styles.content,{paddingTop:insets.top+8}]}>{animatedChildren}</ScrollView></Animated.View>}
export function Header({title,showProfile=true,showBack=true}:{title:string;back?:string;showProfile?:boolean;showBack?:boolean}){const transitions=useTransitions();return <View style={[styles.row,{gap:12,marginBottom:14}]}>{showBack?<Pressable accessibilityRole="button" accessibilityLabel="Go back" onPress={()=>transitions.goBack()} style={{height:40,width:40,borderRadius:13,borderWidth:1,borderColor:C.rule,alignItems:'center',justifyContent:'center'}}><ArrowLeft size={18} color={C.navy}/></Pressable>:null}<Text style={{fontFamily:'Georgia',fontSize:20,color:C.navy,flex:1}}>{title}</Text>{showProfile?<Pressable accessibilityRole="button" accessibilityLabel="Open profile" onPress={()=>transitions.goTo('/profile','profile')} style={{height:40,width:40,borderRadius:13,borderWidth:1,borderColor:C.rule,alignItems:'center',justifyContent:'center'}}><UserRound size={18} color={C.navy}/></Pressable>:null}</View>}
export function BottomNav(){const insets=useSafeAreaInsets();const path=usePathname();const active=path==='/home'?'home':path.split('/')[1];const items=[{key:'home',label:'Home',icon:Home,to:'/home'},{key:'dashboard',label:'Dashboard',icon:BarChart3,to:'/dashboard'},{key:'predict',label:'Predict',icon:TrendingDown,to:'/predict'},{key:'group',label:'Group',icon:Users,to:'/group'}];const indicator=useRef(new Animated.Value(-20)).current;const positions=useRef<Record<string,number>>({});const moveIndicator=(key:string,x:number,width:number)=>{positions.current[key]=x+width/2-2.5;if(key===active)Animated.spring(indicator,{toValue:positions.current[key],useNativeDriver:true,speed:18,bounciness:5}).start()};useEffect(()=>{const x=positions.current[active];if(x!==undefined)Animated.spring(indicator,{toValue:x,useNativeDriver:true,speed:18,bounciness:5}).start()},[active,indicator]);return <View style={{position:'absolute',zIndex:1000,elevation:100,bottom:0,left:0,right:0,height:76+insets.bottom,paddingBottom:Math.max(insets.bottom,7),paddingHorizontal:8,backgroundColor:'#F7F2E9',borderTopWidth:1,borderColor:'rgba(8,22,39,.08)',flexDirection:'row',justifyContent:'space-around',alignItems:'center'}}>{items.slice(0,2).map(x=><NavItem key={x.key} label={x.label} icon={x.icon} to={x.to} active={active===x.key} currentPath={path} onLayout={(layoutX,width)=>moveIndicator(x.key,layoutX,width)}/>)}<Pressable accessibilityRole="button" accessibilityLabel="Scan a receipt" onPress={()=>router.push('/scan')} style={({pressed})=>({height:64,width:64,borderRadius:40,borderWidth:4,borderColor:C.amber,borderBottomWidth:7,borderBottomColor:'#002B53',backgroundColor:C.navy,alignItems:'center',justifyContent:'center',marginTop:-22,transform:[{translateY:pressed?3:0}]})}><Camera color="white" size={24}/></Pressable>{items.slice(2).map(x=><NavItem key={x.key} label={x.label} icon={x.icon} to={x.to} active={active===x.key} currentPath={path} onLayout={(layoutX,width)=>moveIndicator(x.key,layoutX,width)}/>)}<Animated.View pointerEvents="none" style={{position:'absolute',bottom:Math.max(insets.bottom,7),left:0,width:5,height:5,borderRadius:3,backgroundColor:C.amber,transform:[{translateX:indicator}]}}/></View>}
function NavItem({label,icon:Icon,to,active,currentPath,onLayout}:{label:string;icon:any;to:string;active:boolean;currentPath:string;onLayout:(x:number,width:number)=>void}){return <Pressable accessibilityRole="button" onLayout={event=>{const {x,width}=event.nativeEvent.layout;onLayout(x,width)}} onPress={()=>{if(currentPath!==to)DeviceEventEmitter.emit("navTabSelected",to);router.push(to as never)}} style={{width:62,minHeight:50,alignItems:'center',justifyContent:'center',gap:3}}><Icon size={20} color={active?C.navy:'#7B8588'} strokeWidth={2}/><Text style={{fontSize:9,color:active?C.navy:'#7B8588',fontWeight:'600'}}>{label}</Text></Pressable>}export function Chart({values,comparison,animate=false}:{values:number[];comparison?:number[];animate?:boolean}) {
  const w=340,h=145,p=12;
  // Guard SVG from malformed/empty data; react-native-svg rejects NaN coordinates.
  const safeValues=values.map(value=>Number.isFinite(Number(value))?Number(value):0);
  const safeComparison=comparison?.map(value=>Number.isFinite(Number(value))?Number(value):0);
  const plottedValues=safeValues.length?safeValues:[0,0];
  const list=[...plottedValues,...(safeComparison||[])];
  const dataMin=Math.min(...list),dataMax=Math.max(...list),padding=Math.max((dataMax-dataMin)*.1,1);
  const min=dataMin-padding,max=dataMax+padding;
  const point=(v:number,i:number,count:number):[number,number]=>[p+i*(w-p*2)/Math.max(1,count-1),h-p-(v-min)/(max-min)*(h-p*2)];
  const coords=plottedValues.map((v,i)=>point(v,i,plottedValues.length));
  const line=(arr:number[])=>arr.map((v,i)=>{const [x,y]=point(v,i,arr.length);return `${i?'L':'M'} ${x} ${y}`}).join(' ');
  const fullPath=line(plottedValues);
  const startPath=`M ${coords[0][0]} ${coords[0][1]}`;
  const valuesKey=plottedValues.join(',');
  const [drawnPath,setDrawnPath]=React.useState(animate?startPath:fullPath);
  const [visiblePoints,setVisiblePoints]=React.useState(animate?1:plottedValues.length);
  const [drawing,setDrawing]=React.useState(false);
  const [startedKey,setStartedKey]=React.useState(animate?valuesKey:'');
  const pathname=usePathname();
  const [tabRedraw,setTabRedraw]=React.useState(0);
  React.useEffect(()=>{const subscription=DeviceEventEmitter.addListener('navTabSelected',(route:string)=>{if(route===pathname)setTabRedraw(value=>value+1)});return()=>subscription.remove()},[pathname]);
  React.useLayoutEffect(()=>{
    if(!animate&&tabRedraw===0){setDrawnPath(fullPath);setVisiblePoints(plottedValues.length);setDrawing(false);setStartedKey('');return;}
    setStartedKey(valuesKey);setDrawnPath(startPath);setVisiblePoints(1);setDrawing(true);
    let start:number|undefined;
    let frame=0;
    const segmentDuration=230;
    const segmentCount=Math.max(0,coords.length-1);
    const tick=(now:number)=>{
      if(start===undefined)start=now;
      const elapsed=now-start;
      const finished=Math.min(segmentCount,Math.floor(elapsed/segmentDuration));
      const portion=finished>=segmentCount?0:Math.min(1,(elapsed-finished*segmentDuration)/segmentDuration);
      const eased=1-Math.pow(1-portion,3);
      let d=startPath;
      for(let i=1;i<=finished;i++)d+=` L ${coords[i][0]} ${coords[i][1]}`;
      if(finished<segmentCount){
        const from=coords[finished],to=coords[finished+1];
        d+=` L ${from[0]+(to[0]-from[0])*eased} ${from[1]+(to[1]-from[1])*eased}`;
      }
      setDrawnPath(d);setVisiblePoints(finished+1);
      if(elapsed<segmentCount*segmentDuration)frame=requestAnimationFrame(tick);
      else{setDrawnPath(fullPath);setVisiblePoints(plottedValues.length);setDrawing(false);}
    };
    frame=requestAnimationFrame(tick);
    return()=>cancelAnimationFrame(frame);
  },[animate,valuesKey,tabRedraw]);
  const renderPath=animate&&startedKey!==valuesKey?startPath:drawnPath;
  return <View><Svg viewBox={`0 0 ${w} ${h}`} width="100%" height={145}>
    <Line x1={p} y1={h-15} x2={w-p} y2={h-15} stroke="#C9C2B6" strokeWidth="1"/>
    {safeComparison?.length ? <Path d={line(safeComparison)} fill="none" stroke="#87949A" strokeWidth="2" strokeDasharray="4 5"/> : null}
    <Path d={renderPath} fill="none" stroke={C.navy} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
    {plottedValues.slice(0,visiblePoints).map((_v,i)=>{const [x,y]=coords[i];return <Circle key={i} cx={x} cy={y} r="3.5" fill={i===plottedValues.length-1?C.amber:C.linen} stroke={C.navy} strokeWidth="2"/>})}
  </Svg><View style={{flexDirection:'row',justifyContent:'space-between'}}><Text style={styles.tiny}>6 weeks ago</Text><Text style={styles.tiny}>Last week</Text><Text style={styles.tiny}>This week</Text></View></View>
}export function PopIn({children,delay=0,style}:{children:React.ReactNode;delay?:number;style?:object}){const progress=useRef(new Animated.Value(0)).current;useEffect(()=>{const timer=setTimeout(()=>Animated.spring(progress,{toValue:1,useNativeDriver:true,speed:15,bounciness:8}).start(),delay);return()=>clearTimeout(timer);},[delay]);return <Animated.View style={[style,{opacity:progress,transform:[{scale:progress.interpolate({inputRange:[0,1],outputRange:[.86,1]})},{translateY:progress.interpolate({inputRange:[0,1],outputRange:[18,0]})}]}]}>{children}</Animated.View>}
export function CarbonTag({value}:{value:number}){const bg=value<1?'#DCEBD9':value<3?'#FAE8AE':'#F2D5D0',fg=value<1?'#17733A':value<3?'#765700':'#A32822';return <View style={{alignSelf:'flex-start',backgroundColor:bg,borderRadius:9,paddingHorizontal:7,paddingVertical:4,flexDirection:'row',alignItems:'center',gap:4}}><View style={{width:6,height:6,borderRadius:5,backgroundColor:fg}}/><Text style={{fontSize:8,color:fg,fontWeight:'700'}}>{value<1?'Low':value<3?'Med':'High'} · {value.toFixed(1)} kg</Text></View>}
export function CategoryIcon({category}:{category:Category}){const glyph:Record<Category,string>={Groceries:'◒',Dining:'⌁',Household:'⌂',Health:'✚',Transport:'↗',Other:'·'};return <View style={{width:30,height:30,borderRadius:10,backgroundColor:'#E0E4DC',alignItems:'center',justifyContent:'center'}}><Text style={{fontSize:16,color:C.navy,fontWeight:'700'}}>{glyph[category]}</Text></View>}
export function SectionTitle({children,right}:{children:React.ReactNode;right?:React.ReactNode}){return <View style={styles.titleRow}><Text style={styles.h2}>{children}</Text>{right}</View>}
export function Empty({title,copy,action}:{title:string;copy:string;action?:()=>void}){return <View style={{alignItems:'center',paddingVertical:26}}><View style={{height:58,width:58,borderRadius:18,backgroundColor:'#DCE5E2',alignItems:'center',justifyContent:'center',marginBottom:13}}><ReceiptText size={28} color={C.navy}/><View style={{position:'absolute',right:6,top:6,width:12,height:12,borderRadius:10,backgroundColor:C.amber}}/></View><Text style={[styles.h2,{fontSize:19}]}>{title}</Text><Text style={[styles.body,{marginTop:5,marginBottom:12,textAlign:'center'}]}>{copy}</Text>{action&&<Action onPress={action}>Get started</Action>}</View>}
export function ReceiptRow({merchant,date,total,onPress,carbon=1,morphTo}:{merchant:string;date:string;total:number;onPress:()=>void;carbon?:number;morphTo?:string|{pathname:string;params?:Record<string,string>}}){const ref=useRef<View>(null);const transitions=useTransitions();const press=()=>{if(!morphTo){onPress();return;}ref.current?.measureInWindow((x,y,width,height)=>transitions.morphTo(morphTo,{x,y,width,height}));};return <Pressable ref={ref} onPress={press} style={[styles.row,styles.divider,{minHeight:58,gap:10}]}><View style={{width:34,height:34,borderRadius:12,backgroundColor:'#D7DFDE',alignItems:'center',justifyContent:'center'}}><Text style={{fontFamily:'Georgia',fontSize:17,color:C.navy}}>{merchant[0]}</Text></View><View style={{flex:1}}><Text style={{fontSize:12,fontWeight:'700',color:C.ink}}>{merchant}</Text><Text style={styles.tiny}>{dateLabel(date)}</Text></View><View style={{width:8,height:8,borderRadius:6,backgroundColor:carbon>12?C.tomato:C.jungle}}/><Money value={total}/><ChevronRight size={16} color="#8D918D"/></Pressable>}







