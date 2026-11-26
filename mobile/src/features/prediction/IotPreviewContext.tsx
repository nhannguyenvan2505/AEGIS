import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { useAuth } from '../../state/AuthContext';
import { useDemo } from '../../state/DemoContext';
import type { ForecastSource } from './client';
import { fieldReadings, forecastNumber } from './forecastFields';
import { fetchLatestEsp32, type Esp32Alert, type Esp32Reading, type Esp32TelemetryResponse } from './iotClient';
import { createIotPreviewStore, type IotPreviewStore, type IotReadings, type PreviewForecast } from './iotPreview';

export type LiveIotMeta = {
  isLive: boolean;
  deviceUid: string;
  alert: Esp32Alert;
  bindingScope: Esp32TelemetryResponse['binding_scope'];
  mqttConnected: boolean;
  history: Esp32Reading[];
};

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

function buildEsp32Forecast(item: Esp32Reading): PreviewForecast {
  const horizonHours = 72;
  const tone = item.alert.level === 'safe' ? 'low' : 'high';
  const label = tone === 'high' ? (item.alert.level === 'high' ? 'Nguy cơ cao' : 'Cần chú ý') : 'Nguy cơ thấp';
  const conditions = `Nhiệt độ ${forecastNumber(item.temperature)} °C, độ ẩm ${forecastNumber(item.humidity)}% (ESP32 ${item.device_uid})`;
  return {
    status: { label, tone },
    issuedAt: item.observed_at,
    targetWindowEnd: new Date(Date.parse(item.observed_at) + horizonHours * 3600000).toISOString(),
    horizonHours,
    title: item.alert.title,
    explanation: `${conditions}. ${item.alert.message}`,
    outlook: tone === 'high'
      ? 'Theo dõi lá trong 24 giờ tới và kiểm tra độ ẩm ruộng. Đây là cảnh báo vi khí hậu từ cảm biến, chưa xác nhận lúa đã nhiễm bệnh.'
      : 'Điều kiện vi khí hậu từ cảm biến đang ổn định. Tiếp tục theo dõi định kỳ khi thời tiết thay đổi.',
  };
}

export function usePlotIot(plotId?: string, source: ForecastSource | null = null) {
  const store = useContext(Context);
  const { session } = useAuth();
  if (!store) throw new Error('Missing IotPreviewProvider');

  const [liveResponse, setLiveResponse] = useState<{ plotId?: string; data: Esp32TelemetryResponse } | null>(null);
  const token = session?.access_token;

  const pullLive = useCallback(async () => {
    if (!token || !plotId) return;
    try {
      const data = await fetchLatestEsp32(token, plotId, 24);
      setLiveResponse({ plotId, data });
    } catch {
      // Keep the latest snapshot or preview readings when offline/retrying.
    }
  }, [token, plotId]);

  useEffect(() => {
    if (!token || !plotId) return;
    let active = true;
    const sync = () => {
      void fetchLatestEsp32(token, plotId, 24)
        .then(data => { if (active) setLiveResponse({ plotId, data }); })
        .catch(() => {});
    };
    sync();
    const timer = setInterval(sync, 5000);
    return () => { active = false; clearInterval(timer); };
  }, [token, plotId]);

  const refresh = useCallback(() => {
    void pullLive();
  }, [pullLive]);

  const liveData = liveResponse && plotId && liveResponse.plotId === plotId ? liveResponse.data : null;
  const liveItem = liveData?.item ?? null;
  if (liveItem && liveData) {
    const readings: IotReadings = {
      temperature: liveItem.temperature,
      humidity: liveItem.humidity,
      soilPh: null,
      rainfall: null,
      observedAt: liveItem.observed_at,
    };
    const liveIot: LiveIotMeta = {
      isLive: true,
      deviceUid: liveItem.device_uid,
      alert: liveItem.alert,
      bindingScope: liveData.binding_scope,
      mqttConnected: liveData.mqtt.connected,
      history: liveData.items,
    };
    return { readings, forecast: buildEsp32Forecast(liveItem), refresh, liveIot };
  }

  // No live ESP32 reading for this plot: never show the simulated preview frames as if measured.
  return { readings: fieldReadings(source), forecast: undefined, refresh, liveIot: null as LiveIotMeta | null };
}
