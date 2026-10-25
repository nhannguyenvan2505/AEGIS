import { Screen } from '../components/Screen';
import { AlertsScreen } from '../features/alerts/AlertsScreen';
import { useDemo } from '../state/DemoContext';
export default function Page() { const { read, setRead } = useDemo(); return <Screen title="Hộp thư cảnh báo"><AlertsScreen read={read} onRead={() => setRead(true)} /></Screen>; }
