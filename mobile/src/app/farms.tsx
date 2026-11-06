import { Screen } from '../components/Screen';
import { FarmsScreen } from '../features/farms/FarmsScreen';
import { useDemo } from '../state/DemoContext';
import { useAuth } from '../state/AuthContext';
import { ConnectedFarmsScreen } from '../features/farms/ConnectedFarmsScreen';
export default function Page() { const {plots,setPlots}=useDemo(); const { session } = useAuth(); return <Screen title="Quản lý nông trại">{session ? <ConnectedFarmsScreen /> : <FarmsScreen plots={plots} setPlots={setPlots} />}</Screen>; }
