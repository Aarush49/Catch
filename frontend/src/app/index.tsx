import { Redirect } from 'expo-router';import { LoadingState,ErrorState } from '../components/UI';import { useAppStore } from '../store/AppStore';
export default function Index(){const{hydrated,error,user}=useAppStore();if(!hydrated)return <LoadingState label="Loading your data"/>;if(error)return <ErrorState message={error}/>;return <Redirect href={user?'/(tabs)/home':'/auth'}/>}
