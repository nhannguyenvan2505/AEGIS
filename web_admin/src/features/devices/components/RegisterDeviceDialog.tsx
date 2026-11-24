import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api, type Paged } from '../../../core/api/client';
import { ApiError } from '../../../core/api/errors';
import { SENSOR_LABEL } from '../../../shared/status/Badges';
import { Modal } from '../../../shared/ui/Dialogs';
import type { Farm, Plot, Season, SensorSlots } from '../../farms/types';

interface Values { device_code: string; device_name: string; firmware_version: string; protocol: string; sensor_type: string }
const EMPTY: Values = { device_code: '', device_name: '', firmware_version: '', protocol: 'MQTT', sensor_type: '' };

/**
 * Đăng ký thiết bị theo trình tự: nông trại → ruộng → mùa vụ → loại cảm biến còn thiếu.
 * Người dùng không phải tự gõ ID mùa vụ; chỉ các loại cảm biến ruộng đó chưa có mới được chọn.
 */
export function RegisterDeviceDialog({ onClose, onSubmit }: { onClose(): void; onSubmit(body: Record<string, unknown>): Promise<unknown> }) {
  const [farmId, setFarmId] = useState('');
  const [plotId, setPlotId] = useState('');
  const [seasonId, setSeasonId] = useState('');
  const [v, setV] = useState<Values>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const farms = useQuery({ queryKey: ['farms', 'picker'], queryFn: ({ signal }) => api<Paged<Farm>>('/farms', { params: { page_size: 100 }, signal }) });
  const farm = useQuery({ queryKey: ['farms', 'detail', farmId], enabled: Boolean(farmId), queryFn: ({ signal }) => api<{ plots: Plot[] }>(`/farms/${farmId}`, { signal }) });
  const plot = useQuery({
    queryKey: ['farms', 'plot', plotId], enabled: Boolean(plotId),
    queryFn: ({ signal }) => api<{ seasons: Season[]; sensors: SensorSlots }>(`/plots/${plotId}`, { signal }),
  });

  const missing = plot.data?.sensors.missing ?? [];
  const full = Boolean(plotId) && plot.isSuccess && missing.length === 0;
  const set = (patch: Partial<Values>) => setV((x) => ({ ...x, ...patch }));

  const pickFarm = (id: string) => { setFarmId(id); setPlotId(''); setSeasonId(''); set({ sensor_type: '' }); };
  const pickPlot = (id: string) => { setPlotId(id); setSeasonId(''); set({ sensor_type: '' }); };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await onSubmit({
        season_id: seasonId, sensor_type: v.sensor_type, device_code: v.device_code, protocol: v.protocol, source: 'mock',
        device_name: v.device_name || undefined, firmware_version: v.firmware_version || undefined,
      });
      onClose();
    } catch (err) { setError(err); } finally { setBusy(false); }
  };

  return (
    <Modal open title="Đăng ký thiết bị" onClose={onClose}>
      <form onSubmit={submit} className="stack" style={{ gap: 12 }}>
        <label className="field" htmlFor="rd-farm">Nông trại *
          <select id="rd-farm" value={farmId} required onChange={(e) => pickFarm(e.target.value)}>
            <option value="">— Chọn nông trại —</option>
            {farms.data?.items.map((f) => <option key={f.id} value={f.id}>{f.name} · {f.owner_email}</option>)}
          </select>
        </label>
        <label className="field" htmlFor="rd-plot">Ruộng *
          <select id="rd-plot" value={plotId} required disabled={!farmId} onChange={(e) => pickPlot(e.target.value)}>
            <option value="">{farmId ? '— Chọn ruộng —' : 'Chọn nông trại trước'}</option>
            {farm.data?.plots.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.sensor_count}/4 cảm biến)</option>)}
          </select>
        </label>
        <label className="field" htmlFor="rd-season">Mùa vụ *
          <select id="rd-season" value={seasonId} required disabled={!plotId} onChange={(e) => setSeasonId(e.target.value)}>
            <option value="">{plotId ? '— Chọn mùa vụ —' : 'Chọn ruộng trước'}</option>
            {plot.data?.seasons.map((s) => <option key={s.id} value={s.id}>{s.name} · {s.status}</option>)}
          </select>
          {plot.isSuccess && plot.data.seasons.length === 0 && <span className="small muted" style={{ fontWeight: 400 }}>Ruộng này chưa có mùa vụ. Cần tạo mùa vụ trên app mobile trước.</span>}
        </label>
        <label className="field" htmlFor="rd-sensor">Loại cảm biến *
          <select id="rd-sensor" value={v.sensor_type} required disabled={!plotId || full} onChange={(e) => set({ sensor_type: e.target.value })}>
            <option value="">{full ? 'Ruộng đã đủ 4 loại' : '— Chọn loại còn thiếu —'}</option>
            {missing.map((t) => <option key={t} value={t}>{SENSOR_LABEL[t] ?? t}</option>)}
          </select>
          {plotId && !full && <span className="small muted" style={{ fontWeight: 400 }}>Chỉ hiện loại ruộng này chưa có ({missing.length} loại còn thiếu).</span>}
        </label>
        <label className="field" htmlFor="rd-code">Mã thiết bị *
          <input id="rd-code" value={v.device_code} required autoComplete="off" onChange={(e) => set({ device_code: e.target.value })} />
          <span className="small muted" style={{ fontWeight: 400 }}>Chữ, số, dấu . _ - (tối đa 64), không trùng với thiết bị khác của khách này.</span>
        </label>
        <label className="field" htmlFor="rd-name">Tên thiết bị
          <input id="rd-name" value={v.device_name} autoComplete="off" onChange={(e) => set({ device_name: e.target.value })} />
        </label>
        <label className="field" htmlFor="rd-fw">Phiên bản firmware
          <input id="rd-fw" value={v.firmware_version} placeholder="ví dụ 1.0.3" autoComplete="off" onChange={(e) => set({ firmware_version: e.target.value })} />
          <span className="small muted" style={{ fontWeight: 400 }}>Phiên bản phần mềm nạp trong thiết bị. Có thể để trống.</span>
        </label>
        <label className="field" htmlFor="rd-protocol">Giao thức *
          <select id="rd-protocol" value={v.protocol} required onChange={(e) => set({ protocol: e.target.value })}>
            <option value="MQTT">MQTT</option>
            <option value="HTTP">HTTP</option>
          </select>
        </label>
        {error !== null && <div className="error-box" role="alert">{error instanceof ApiError ? error.message : 'Đã xảy ra lỗi.'}</div>}
        <div className="dialog-actions">
          <button type="button" className="btn secondary" onClick={onClose} disabled={busy}>Hủy</button>
          <button type="submit" className="btn" disabled={busy || full}>{busy ? 'Đang lưu…' : 'Đăng ký'}</button>
        </div>
      </form>
    </Modal>
  );
}
