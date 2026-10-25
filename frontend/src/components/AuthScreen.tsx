import React from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ArrowRight, LockKeyhole, Mail, User } from 'lucide-react-native';
import { C, styles } from './tally';

type AuthScreenProps = {
  mode: 'login' | 'signup';
  email: string;
  password: string;
  name?: string;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onNameChange?: (value: string) => void;
  onSubmit: () => void;
  onSwitch: () => void;
};

export function AuthScreen({ mode, email, password, name = '', onEmailChange, onPasswordChange, onNameChange, onSubmit, onSwitch }: AuthScreenProps) {
  const signup = mode === 'signup';
  return <SafeAreaView style={{ flex: 1, backgroundColor: C.linen }}>
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ flexGrow: 1, paddingHorizontal: 24, paddingVertical: 22 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <View style={{ height: 34, width: 34, borderRadius: 11, backgroundColor: C.navy, alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontFamily: 'Georgia', fontSize: 21, color: C.amber, fontWeight: '700' }}>C</Text></View>
          <Text style={{ fontSize: 22, fontWeight: '700', color: C.navy }}>CATch</Text>
        </View>

        <View style={{ flex: 1, justifyContent: 'center', paddingVertical: 36 }}>
          <Text style={styles.eyebrow}>{signup ? 'YOUR MONEY, MADE CLEAR' : 'NICE TO SEE YOU AGAIN'}</Text>
          <Text style={[styles.h1, { fontSize: 43, lineHeight: 46 }]}>{signup ? 'Start catching\n' : 'Welcome\n'}<Text style={{ color: C.tomato, fontStyle: 'italic' }}>{signup ? 'the little things.' : 'back.'}</Text></Text>
          <Text style={[styles.body, { fontSize: 13, lineHeight: 19, marginTop: 12, marginBottom: 26 }]}>{signup ? 'See where your money goes, what it could become, and the impact it leaves behind.' : 'Sign in to see your purchases, plans, and shared groups.'}</Text>

          {signup && <Field icon={User} label="NAME" value={name} placeholder="Alex Morgan" onChangeText={onNameChange!} autoCapitalize="words" />}
          <Field icon={Mail} label="EMAIL" value={email} placeholder="you@example.com" onChangeText={onEmailChange} keyboardType="email-address" autoCapitalize="none" />
          <Field icon={LockKeyhole} label="PASSWORD" value={password} placeholder={signup ? 'At least 8 characters' : 'Your password'} onChangeText={onPasswordChange} secureTextEntry />

          {!signup && <Pressable style={{ alignSelf: 'flex-end', paddingVertical: 7 }}><Text style={{ fontSize: 10, fontWeight: '700', color: C.navy }}>Forgot password?</Text></Pressable>}
          <Pressable onPress={onSubmit} style={({ pressed }) => ({ minHeight: 54, borderRadius: 16, backgroundColor: C.navy, borderBottomWidth: pressed ? 1 : 5, borderBottomColor: '#002B53', transform: [{ translateY: pressed ? 4 : 0 }], flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 12 })}>
            <Text style={{ color: 'white', fontSize: 13, fontWeight: '700' }}>{signup ? 'Create my account' : 'Sign in'}</Text><ArrowRight size={17} color={C.amber} />
          </Pressable>

          <View style={{ flexDirection: 'row', justifyContent: 'center', alignItems: 'center', marginTop: 20 }}>
            <Text style={{ fontSize: 11, color: C.muted }}>{signup ? 'Already have an account? ' : 'New to CATch? '}</Text>
            <Pressable onPress={onSwitch}><Text style={{ fontSize: 11, color: C.navy, fontWeight: '700' }}>{signup ? 'Sign in' : 'Create an account'}</Text></Pressable>
          </View>
        </View>

        <View style={{ backgroundColor: '#F3EEE5', borderRadius: 16, padding: 14, flexDirection: 'row', gap: 10, alignItems: 'center' }}>
          <View style={{ height: 9, width: 9, borderRadius: 6, backgroundColor: C.jungle }} />
          <Text style={{ fontSize: 10, lineHeight: 15, color: C.muted, flex: 1 }}>Your demo data stays on this device. Small choices, safely kept.</Text>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  </SafeAreaView>;
}

function Field({ icon: Icon, label, ...props }: React.ComponentProps<typeof TextInput> & { icon: typeof Mail; label: string }) {
  return <View style={{ marginBottom: 15 }}><Text style={[styles.eyebrow, { marginBottom: 6 }]}>{label}</Text><View style={{ minHeight: 52, borderWidth: 1, borderColor: '#C9C4B9', backgroundColor: '#F7F3EB', borderRadius: 15, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, gap: 10 }}><Icon size={17} color={C.navy} /><TextInput {...props} placeholderTextColor="#929994" style={{ flex: 1, fontSize: 13, color: C.ink, paddingVertical: 12 }} /></View></View>;
}
