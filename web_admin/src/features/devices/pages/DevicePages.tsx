import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../../../core/api/client';
import { useAuth } from '../../../core/auth/AuthContext';
import { formatDateTime } from '../../../core/utils/format';
import { MultiLine } from '../../../shared/charts/Charts';
import { DataTable, FilterBar, Pagination } from '../../../shared/data-table/DataTable';
import { ErrorState, LoadingState, SimulatedDataBanner } from '../../../shared/feedback/Feedback';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { DeviceStatusBadge, SENSOR_OPTIONS, SensorTag, SourceTag } from '../../../shared/status/Badges';
import { Card, KeyValue } from '../../../shared/ui/Card';
import { UserCell } from '../../../shared/ui/UserCell';
import { ConfirmDialog, FormDialog, type FormValues } from '../../../shared/ui/Dialogs';
import { useAction } from '../../../shared/hooks/useAction';
import { usePagedQuery } from '../../../shared/hooks/usePagedQuery';
import { useUrlFilters } from '../../../shared/hooks/useUrlFilters';
import { RegisterDeviceDialog } from '../components/RegisterDeviceDialog';
import type { Device, Esp32TelemetryResponse, TelemetryPoint } from '../types';

const KEYS = ['user', 'q', 'sensor_type', 'status', 'source'] as const;
const STATUS = [['online', 'Online'], ['offline', 'Offline'], ['maintenance', 'Bảo trì'], ['inactive', 'Ngừng']].map(([value, label]) => ({ value, label }));

export function DeviceListPage() {
  const navigate = useNavigate();
  const { can } = useAuth();
  const { filters, page, setFilter, setPage } = useUrlFilters(KEYS);
  const query = usePagedQuery<Device>('devices', '/devices', filters, page);
  const esp32 = useQuery({
    queryKey: ['devices', 'esp32'],
    queryFn: ({ signal }) => api<Esp32TelemetryResponse>('/iot/readings', { params: { limit: 24 }, signal }),
    refetchInterval: 5000,
  });
  const [creating, setCreating] = useState(false);
  const create = useAction((body: Record<string, unknown>) => api('/devices', { method: 'POST', body }),
    { invalidate: ['devices', 'stats', 'farms'], success: 'Đã đăng ký thiết bị.' });
  const espSeries = [...(esp32.data?.items ?? [])].reverse().map((p) => ({
    time: formatDateTime(p.observed_at).slice(0, 17),
    temp: p.temperature,
    humidity: p.humidity,
  }));
  return (
    <>
      <PageHeader title="Thiết bị IoT" actions={can('admin') && <button className="btn" onClick={() => setCreating(true)}>Đăng ký thiết bị</button>} />
      <Card title="Dữ liệu cảm biến ESP32 thực tế (MQTT)">
        {esp32.isLoading && <LoadingState rows={2} />}
        {esp32.isError && <ErrorState error={esp32.error} onRetry={() => void esp32.refetch()} />}
        {esp32.data && (
          <>
            <KeyValue rows={[
              ['Broker MQTT', `${esp32.data.mqtt.broker}:${esp32.data.mqtt.port} (${esp32.data.mqtt.topic})`],
              ['Trạng thái kết nối', esp32.data.mqtt.connected ? 'Đã kết nối' : 'Chưa kết nối'],
              ['Số gói tin đã nhận', String(esp32.data.mqtt.received_count)],
              ['Thiết bị ESP32 mới nhất', esp32.data.item ? `${esp32.data.item.device_uid} · ${esp32.data.item.temperature} °C · ${esp32.data.item.humidity}% (${esp32.data.item.alert.title})` : 'Chưa có gói tin từ ESP32'],
            ]} />
            {espSeries.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <MultiLine data={espSeries} x="time" label="Nhiệt độ và độ ẩm ESP32 thực tế"
                  lines={[{ key: 'temp', name: 'Nhiệt độ (°C)', color: '#d98b1b' }, { key: 'humidity', name: 'Độ ẩm (%)', color: '#1d5fa8' }]} />
              </div>
            )}
          </>
        )}
      </Card>
      <SimulatedDataBanner>Danh sách thiết bị và telemetry nguồn mock/synthetic bên dưới là dữ liệu mô phỏng.</SimulatedDataBanner>
      <Card>
        <FilterBar values={filters} onChange={setFilter} defs={[
          { name: 'user', label: 'Người dùng', placeholder: 'Tên hoặc email' },
          { name: 'q', label: 'Tìm kiếm', placeholder: 'Mã hoặc tên thiết bị' },
          { name: 'sensor_type', label: 'Loại cảm biến', type: 'select', options: SENSOR_OPTIONS },
          { name: 'status', label: 'Trạng thái', type: 'select', options: STATUS },
          { name: 'source', label: 'Nguồn', type: 'select', options: ['mock', 'synthetic', 'field', 'bench', 'legacy'].map((v) => ({ value: v, label: v })) },
        ]} />
        <DataTable rows={query.data?.items} loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()}
          rowKey={(d) => d.id} onRowClick={(d) => navigate(`/devices/${d.id}`)}
          columns={[
            { header: 'Mã thiết bị', cell: (d) => <><strong>{d.device_code}</strong>{d.device_uid && d.device_uid !== d.id && !/^(mock:|raw:|released:)/i.test(d.device_uid) && <div className="small muted">UID: {d.device_uid}</div>}</> },
            { header: 'Cảm biến', cell: (d) => <SensorTag value={d.sensor_type} /> }, { header: 'Ruộng', cell: (d) => d.plot_name ?? '—' }, { header: 'Chủ sở hữu', cell: (d) => <UserCell name={d.owner_name} email={d.owner_email} /> },
            { header: 'Giao thức', cell: (d) => d.protocol }, { header: 'Trạng thái', cell: (d) => <DeviceStatusBadge value={d.status} /> },
            { header: 'Nguồn', cell: (d) => <SourceTag source={d.source} /> }, { header: 'Thấy lần cuối', cell: (d) => formatDateTime(d.last_seen_at) },
          ]} />
        {query.data && <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPage={setPage} />}
      </Card>
      {creating && <RegisterDeviceDialog onClose={() => setCreating(false)} onSubmit={create} detectedUids={esp32.data?.devices.map((x) => x.device_uid).filter((u) => u && u.toLowerCase() !== 'unknown')} />}
    </>
  );
}

export function DeviceDetailPage() {
  const { id = '' } = useParams();
  const { can } = useAuth();
  const dev = useQuery({ queryKey: ['devices', 'detail', id], queryFn: ({ signal }) => api<{ device: Device }>(`/devices/${id}`, { signal }) });
  const deviceRow = dev.data?.device;
  const hasHardwareUid = Boolean(deviceRow?.device_uid && deviceRow.device_uid !== deviceRow.id && !/^(mock:|raw:|released:)/i.test(deviceRow.device_uid));
  const tel = useQuery({
    queryKey: ['devices', 'telemetry', id],
    enabled: Boolean(deviceRow) && !hasHardwareUid,
    queryFn: ({ signal }) => api<{ items: TelemetryPoint[] }>(`/devices/${id}/telemetry`, { signal }),
  });
  const liveTel = useQuery({
    queryKey: ['devices', 'esp32', deviceRow?.device_uid],
    enabled: hasHardwareUid,
    queryFn: ({ signal }) => api<Esp32TelemetryResponse>('/iot/readings', { params: { device_uid: deviceRow!.device_uid, limit: 50 }, signal }),
    refetchInterval: 5000,
  });
  const [editing, setEditing] = useState(false);
  const [releasing, setReleasing] = useState(false);
  const update = useAction((v: FormValues) => api(`/devices/${id}`, { method: 'PUT', body: { device_name: v.device_name, firmware_version: v.firmware_version, status: v.status, sensor_type: v.sensor_type || undefined } }),
    { invalidate: ['devices', 'stats', 'farms'], success: 'Đã cập nhật thiết bị.' });
  const release = useAction(() => api(`/devices/${id}/release`, { method: 'POST' }),
    { invalidate: ['devices', 'stats', 'farms'], success: 'Đã gỡ đăng ký phần cứng ESP32.' });

  if (dev.isLoading) return <LoadingState />;
  if (dev.isError) return <ErrorState error={dev.error} onRetry={() => void dev.refetch()} />;
  const d = dev.data!.device;
  const series = hasHardwareUid
    ? [...(liveTel.data?.items ?? [])].reverse().map((p) => ({
        time: formatDateTime(p.observed_at).slice(0, 17), temp: p.temperature, humidity: p.humidity,
      }))
    : [...(tel.data?.items ?? [])].reverse().map((p) => ({
        time: formatDateTime(p.start_at).slice(0, 17), temp: p.air_temperature_c, humidity: p.relative_humidity_pct,
      }));
  return (
    <>
      <PageHeader title={d.device_code} crumbs={[{ label: 'Thiết bị', to: '/devices' }, { label: d.device_code }]}
        actions={can('admin') && (
          <div style={{ display: 'flex', gap: 8 }}>
            {hasHardwareUid && <button className="btn danger" onClick={() => setReleasing(true)}>Gỡ đăng ký phần cứng</button>}
            <button className="btn secondary" onClick={() => setEditing(true)}>Sửa / đổi trạng thái</button>
          </div>
        )} />
      {d.is_simulated && <SimulatedDataBanner />}
      <Card title="Thông tin">
        <KeyValue rows={[
          ['Trạng thái', <DeviceStatusBadge value={d.status} />], ['Loại cảm biến', <SensorTag value={d.sensor_type} />], ['Nguồn', <SourceTag source={d.source} />],
          ['ID phần cứng (device_uid)', hasHardwareUid ? d.device_uid : '—'],
          ['Tên', d.device_name], ['Giao thức', d.protocol], ['Firmware', d.firmware_version],
          ['Ruộng', d.plot_id ? <Link to={`/plots/${d.plot_id}`}>{d.plot_name}</Link> : null], ['Mùa vụ', d.season_id ? <Link to={`/seasons/${d.season_id}`}>{d.season_name}</Link> : null],
          ['Chủ sở hữu', d.owner_email], ['Thấy lần cuối', formatDateTime(d.last_seen_at)], ['Tạo lúc', formatDateTime(d.created_at)],
        ]} />
      </Card>
      <Card title={hasHardwareUid ? 'Dữ liệu ESP32 thực tế' : 'Telemetry theo giờ (mô phỏng)'}>
        {(hasHardwareUid ? liveTel.isError : tel.isError)
          ? <ErrorState error={(hasHardwareUid ? liveTel.error : tel.error)!} />
          : <MultiLine data={series} x="time" label={hasHardwareUid ? 'Nhiệt độ và độ ẩm ESP32 thực tế' : 'Nhiệt độ và độ ẩm theo giờ'}
              lines={[{ key: 'temp', name: 'Nhiệt độ (°C)', color: '#d98b1b' }, { key: 'humidity', name: 'Độ ẩm (%)', color: '#1d5fa8' }]} />}
      </Card>
      {editing && (
        <FormDialog open title="Sửa thiết bị" onClose={() => setEditing(false)} onSubmit={update}
          initial={{ device_name: d.device_name ?? '', firmware_version: d.firmware_version ?? '', status: d.status, sensor_type: d.sensor_type ?? '' }}
          fields={[{ name: 'device_name', label: 'Tên' }, { name: 'firmware_version', label: 'Firmware' }, { name: 'status', label: 'Trạng thái', type: 'select', required: true, options: STATUS },
            { name: 'sensor_type', label: 'Loại cảm biến', type: 'select', options: SENSOR_OPTIONS }]} />
      )}
      {releasing && (
        <ConfirmDialog open danger title="Gỡ đăng ký phần cứng ESP32" confirmLabel="Gỡ đăng ký"
          message={<>Gỡ ID phần cứng <strong>{d.device_uid}</strong> khỏi ruộng <strong>{d.plot_name ?? 'hiện tại'}</strong>? Dữ liệu đo cũ vẫn được giữ lại cho chủ cũ, còn mạch ESP32 có thể đăng ký cho ruộng/mùa vụ khác.</>}
          onConfirm={() => release(undefined)} onClose={() => setReleasing(false)} />
      )}
    </>
  );
}
