import { createContext, useCallback, useContext, useState, useSyncExternalStore, type ReactNode } from 'react';
import { useAuth } from '../../state/AuthContext';
import { useDemo } from '../../state/DemoContext';
import type { ForecastSource } from './client';
import { fieldReadings } from './forecastFields';
import { createIotPreviewStore, IOT_PREVIEW_ENABLED, type IotPreviewStore } from './iotPreview';

const Context = createContext<IotPreviewStore | null>(null);

function ScopedIotProvider({ children }: { children: ReactNode }) {
  const [store] = useState(createIotPreviewStore);
  return <Context.Provider value={store}>{children}</Context.Provider>;
}

export function IotPreviewProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const { generation } = useDemo();
  return <ScopedIotProvider key={session?.user.id ?? `iot-demo-${generation}`}>{children}</ScopedIotProvider>;
}

export function usePlotIot(plotId?: string, source: ForecastSource | null = null) {
  const store = useContext(Context);
  if (!store) throw new Error('Missing IotPreviewProvider');
  const subscribe = useCallback((listener: () => void) => IOT_PREVIEW_ENABLED && plotId
    ? store.subscribe(plotId, listener) : () => {}, [store, plotId]);
  const getSnapshot = useCallback(() => IOT_PREVIEW_ENABLED && plotId ? store.get(plotId) : null, [store, plotId]);
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const refresh = useCallback(() => {
    if (IOT_PREVIEW_ENABLED && plotId) store.refresh(plotId);
  }, [store, plotId]);
  return { readings: snapshot?.readings ?? fieldReadings(source), forecast: snapshot?.forecast, refresh };
}
