import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../../../core/api/client';
import { useAuth } from '../../../core/auth/AuthContext';
import { formatDateTime, formatNumber } from '../../../core/utils/format';
import { DataTable, FilterBar, Pagination } from '../../../shared/data-table/DataTable';
import { ErrorState, LoadingState } from '../../../shared/feedback/Feedback';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { DeviceStatusBadge, SENSOR_LABEL, SensorTag, SourceTag } from '../../../shared/status/Badges';
import { Card, JsonView, KeyValue } from '../../../shared/ui/Card';
import { UserCell } from '../../../shared/ui/UserCell';
import { usePagedQuery } from '../../../shared/hooks/usePagedQuery';
import { useUrlFilters } from '../../../shared/hooks/useUrlFilters';
import type { Farm, Plot, PlotDevice, Season, SensorSlots, SeasonDetail } from '../types';

const KEYS = ['user', 'q'] as const;

function Owner({ id, email }: { id: string; email: string }) {
  const { can } = useAuth();
  return can('admin') ? <Link to={`/users/${id}`}>{email}</Link> : <>{email}</>;
}

export function FarmListPage() {
  const navigate = useNavigate();
  const { filters, page, setFilter, setPage } = useUrlFilters(KEYS);
  const query = usePagedQuery<Farm>('farms', '/farms', filters, page);
  return (
    <>
      <PageHeader title="Nông trại" subtitle="Toàn hệ thống (chỉ xem — việc sửa do nông dân làm trên mobile)" />
      <Card>
        <FilterBar values={filters} onChange={setFilter} defs={[{ name: 'user', label: 'Người dùng', placeholder: 'Tên hoặc email' }, { name: 'q', label: 'Tìm kiếm', placeholder: 'Tên hoặc địa chỉ' }]} />
        <DataTable rows={query.data?.items} loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()}
          rowKey={(f) => f.id} onRowClick={(f) => navigate(`/farms/${f.id}`)}
          columns={[
            { header: 'Nông trại', cell: (f) => <strong>{f.name}</strong> },
            { header: 'Chủ sở hữu', cell: (f) => <UserCell name={f.owner_name} email={f.owner_email} /> },
            { header: 'Địa chỉ', cell: (f) => f.address || '—' },
            { header: 'Số ruộng', cell: (f) => f.plot_count },
            { header: 'Diện tích (ha)', cell: (f) => formatNumber(f.area_ha, 2) },
          ]} />
        {query.data && <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPage={setPage} />}
      </Card>
    </>
  );
}

export function FarmDetailPage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const q = useQuery({ queryKey: ['farms', 'detail', id], queryFn: ({ signal }) => api<{ farm: Farm; plots: Plot[] }>(`/farms/${id}`, { signal }) });
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const { farm, plots } = q.data!;
  return (
    <>
      <PageHeader title={farm.name} crumbs={[{ label: 'Nông trại', to: '/farms' }, { label: farm.name }]} />
      <Card title="Thông tin">
        <KeyValue rows={[
          ['Chủ sở hữu', <Owner id={farm.owner_id} email={farm.owner_email} />], ['Quản lý', farm.manager], ['Địa chỉ', farm.address],
          ['Tọa độ', farm.latitude !== null && farm.longitude !== null ? `${farm.latitude}, ${farm.longitude}` : 'Chưa có'],
          ['Ghi chú', farm.notes], ['Tạo lúc', formatDateTime(farm.created_at)],
        ]} />
      </Card>
      <Card title={`Ruộng (${plots.length})`}>
        <DataTable rows={plots} rowKey={(p) => p.id} onRowClick={(p) => navigate(`/plots/${p.id}`)}
          columns={[
            { header: 'Tên', cell: (p) => <strong>{p.name}</strong> }, { header: 'Cây trồng', cell: (p) => p.crop_type },
            { header: 'Diện tích (ha)', cell: (p) => formatNumber(p.area_ha, 2) }, { header: 'Cảm biến', cell: (p) => `${p.sensor_count}/4` }, { header: 'Trạng thái', cell: (p) => p.status },
          ]} />
      </Card>
    </>
  );
}

export function PlotDetailPage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const q = useQuery({ queryKey: ['farms', 'plot', id], queryFn: ({ signal }) => api<{ plot: Plot; seasons: Season[]; devices: PlotDevice[]; sensors: SensorSlots }>(`/plots/${id}`, { signal }) });
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const { plot, seasons, devices, sensors } = q.data!;
  return (
    <>
      <PageHeader title={plot.name} crumbs={[{ label: 'Nông trại', to: '/farms' }, { label: plot.farm_name, to: `/farms/${plot.farm_id}` }, { label: plot.name }]} />
      <Card title="Thông tin">
        <KeyValue rows={[['Chủ sở hữu', <Owner id={plot.owner_id} email={plot.owner_email} />], ['Cây trồng', plot.crop_type], ['Loại đất', plot.soil_type],
          ['Diện tích (ha)', formatNumber(plot.area_ha, 2)], ['Vị trí', plot.location_text], ['Trạng thái', plot.status]]} />
      </Card>
      <Card title={`Cảm biến: ${sensors.installed}/${sensors.expected}`}>
        {sensors.missing.length > 0 && <p className="small muted">Còn thiếu: {sensors.missing.map((t) => SENSOR_LABEL[t] ?? t).join(', ')}. Thêm thiết bị ở trang Thiết bị khi lắp thêm.</p>}
        <DataTable rows={devices} rowKey={(d) => d.id} onRowClick={(d) => navigate(`/devices/${d.id}`)}
          columns={[
            { header: 'Cảm biến', cell: (d) => <SensorTag value={d.sensor_type} /> }, { header: 'Mã', cell: (d) => <strong>{d.device_code}</strong> },
            { header: 'Trạng thái', cell: (d) => <DeviceStatusBadge value={d.status} /> }, { header: 'Thấy lần cuối', cell: (d) => formatDateTime(d.last_seen_at) },
          ]} />
      </Card>
      <Card title={`Mùa vụ (${seasons.length})`}>
        <DataTable rows={seasons} rowKey={(s) => s.id} onRowClick={(s) => navigate(`/seasons/${s.id}`)}
          columns={[
            { header: 'Tên', cell: (s) => <strong>{s.name}</strong> }, { header: 'Cây trồng', cell: (s) => `${s.crop_type}${s.variety ? ` · ${s.variety}` : ''}` },
            { header: 'Bắt đầu', cell: (s) => s.start_date }, { header: 'Kết thúc dự kiến', cell: (s) => s.expected_end_date ?? '—' }, { header: 'Trạng thái', cell: (s) => s.status },
          ]} />
      </Card>
    </>
  );
}

export function SeasonDetailPage() {
  const { id = '' } = useParams();
  const q = useQuery({ queryKey: ['farms', 'season', id], queryFn: ({ signal }) => api<SeasonDetail>(`/seasons/${id}`, { signal }) });
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const { season, devices, revisions, cultivation_profile } = q.data!;
  return (
    <>
      <PageHeader title={season.name} crumbs={[{ label: 'Nông trại', to: '/farms' }, { label: season.plot_name, to: `/plots/${season.plot_id}` }, { label: season.name }]} />
      <Card title="Thông tin">
        <KeyValue rows={[['Cây trồng', `${season.crop_type}${season.variety ? ` · ${season.variety}` : ''}`], ['Bắt đầu', season.start_date],
          ['Kết thúc dự kiến', season.expected_end_date], ['Kết thúc thực tế', season.actual_end_date], ['Trạng thái', season.status], ['Ghi chú', season.notes]]} />
      </Card>
      <div className="grid-2">
        <Card title="Thiết bị">
          <DataTable rows={devices} rowKey={(d) => d.id} empty="Chưa có thiết bị."
            columns={[{ header: 'Mã', cell: (d) => <Link to={`/devices/${d.id}`}>{d.device_code}</Link> }, { header: 'Cảm biến', cell: (d) => <SensorTag value={d.sensor_type} /> }, { header: 'Trạng thái', cell: (d) => <DeviceStatusBadge value={d.status} /> }, { header: 'Nguồn', cell: (d) => <SourceTag source={d.source} /> }]} />
        </Card>
        <Card title="Hồ sơ canh tác (bản mới nhất)"><JsonView value={cultivation_profile} /></Card>
      </div>
      <Card title="Lịch sử chỉnh sửa hồ sơ">
        <DataTable rows={revisions} rowKey={(r) => r.revision} empty="Chưa có bản chỉnh sửa."
          columns={[{ header: 'Bản', cell: (r) => r.revision }, { header: 'Lý do', cell: (r) => r.change_reason ?? '—' }, { header: 'Lúc', cell: (r) => formatDateTime(r.created_at) }, { header: 'SHA-256', cell: (r) => <span className="mono">{r.profile_sha256.slice(0, 12)}…</span> }]} />
      </Card>
    </>
  );
}
