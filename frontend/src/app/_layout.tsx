import React from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { TallyProvider } from '../store/TallyProvider';
import { useFonts, DMSans_400Regular, DMSans_500Medium, DMSans_700Bold } from '@expo-google-fonts/dm-sans';
import { ActivityIndicator, View } from 'react-native';
export default function RootLayout(){const [loaded]=useFonts({DMSans_400Regular,DMSans_500Medium,DMSans_700Bold});if(!loaded)return <View style={{flex:1,alignItems:'center',justifyContent:'center',backgroundColor:'#EAE4D9'}}><ActivityIndicator color="#003A70"/></View>;return <TallyProvider><StatusBar style="dark"/><Stack screenOptions={{headerShown:false,animation:'fade',contentStyle:{backgroundColor:'#EAE4D9'}}}/></TallyProvider>}
