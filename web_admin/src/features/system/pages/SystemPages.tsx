import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../../../core/api/client';
import { formatDateTime } from '../../../core/utils/format';
import { DataTable, FilterBar, Pagination } from '../../../shared/data-table/DataTable';
import { ErrorState, LoadingState } from '../../../shared/feedback/Feedback';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { Card, JsonView } from '../../../shared/ui/Card';
import { FormDialog, type FormValues } from '../../../shared/ui/Dialogs';
import { useAction } from '../../../shared/hooks/useAction';
import { usePagedQuery } from '../../../shared/hooks/usePagedQuery';
import { useUrlFilters } from '../../../shared/hooks/useUrlFilters';

interface Service { status: 'ok' | 'down' | 'error'; latency_ms: number }
interface Health { mysql: Service; ai: Service; forecast: Service; outbox: { pending: number; max_attempts: number }; migrations: { version: number; status: string }[]; note: string }

function ServiceCard({ name, s, hint }: { name: string; s: Service; hint?: string }) {
  const ok = s.status === 'ok';
  return (
    <div className="card kpi"><div className="label">{name}</div>
      <div className="value" style={{ color: ok ? '#0b7a54' : '#b42318' }}>{ok ? 'Hoạt động' : s.status === 'down' ? 'Không phản hồi' : 'Lỗi'}</div>
      <div className="hint">{s.latency_ms} ms{hint ? ` · ${hint}` : ''}</div></div>
  );
}

export function HealthPage() {
  const q = useQuery({ queryKey: ['system', 'health'], queryFn: ({ signal }) => api<Health>('/system/health', { signal }), refetchInterval: 30_000 });
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const h = q.data!;
  return (
    <>
      <PageHeader title="Sức khỏe hệ thống" subtitle="Tự làm mới mỗi 30 giây" actions={<button className="btn secondary" onClick={() => void q.refetch()}>Làm mới</button>} />
      <div className="grid-kpi">
        <ServiceCard name="MySQL" s={h.mysql} />
        <ServiceCard name="Dịch vụ AI (nhận diện ảnh)" s={h.ai} hint="cổng 8000" />
        <ServiceCard name="Worker dự báo" s={h.forecast} hint="cổng 8001" />
        <div className="card kpi"><div className="label">Hàng đợi MongoDB</div><div className="value">{h.outbox.pending}</div><div className="hint">chờ giao · thử tối đa {h.outbox.max_attempts} lần</div></div>
      </div>
      <p className="muted small">{h.note} Dịch vụ AI/dự báo không chạy là bình thường nếu chưa bật chúng.</p>
      <Card title="Phiên bản migration"><DataTable rows={h.migrations} rowKey={(m) => m.version} columns={[{ header: 'Phiên bản', cell: (m) => m.version }, { header: 'Trạng thái', cell: (m) => m.status }]} /></Card>
    </>
  );
}

interface Setting { key: string; value: string; value_type: string; description: string | null; updated_at: string }

export function SettingsPage() {
  const q = useQuery({ queryKey: ['settings', 'list'], queryFn: ({ signal }) => api<{ items: Setting[] }>('/settings', { signal }) });
  const [editing, setEditing] = useState<Setting | 'new' | null>(null);
  const save = useAction((v: FormValues) => api(`/settings/${encodeURIComponent(String(v.key))}`, { method: 'PUT', body: { value: v.value, value_type: v.value_type, description: v.description || undefined } }), { invalidate: ['settings'], success: 'Đã lưu cấu hình.' });
  const types = ['string', 'integer', 'decimal', 'boolean', 'json'].map((v) => ({ value: v, label: v }));
  return (
    <>
      <PageHeader title="Cấu hình hệ thống" subtitle="Lưu trong bảng system_settings; mọi thay đổi được ghi nhật ký" actions={<button className="btn" onClick={() => setEditing('new')}>Thêm / sửa theo khóa</button>} />
      <Card>
        <DataTable rows={q.data?.items} loading={q.isLoading} error={q.error} onRetry={() => void q.refetch()} rowKey={(s) => s.key} empty="Chưa có cấu hình nào."
          columns={[
            { header: 'Khóa', cell: (s) => <span className="mono"><strong>{s.key}</strong></span> }, { header: 'Giá trị', cell: (s) => <span className="mono">{s.value}</span> }, { header: 'Kiểu', cell: (s) => s.value_type },
            { header: 'Mô tả', cell: (s) => s.description ?? '—' }, { header: 'Cập nhật', cell: (s) => formatDateTime(s.updated_at) },
            { header: '', cell: (s) => <button className="btn secondary small" onClick={() => setEditing(s)}>Sửa</button> },
          ]} />
      </Card>
      {editing && (
        <FormDialog open title="Cấu hình" onClose={() => setEditing(null)} onSubmit={save}
          initial={editing === 'new' ? { value_type: 'string' } : { key: editing.key, value: editing.value, value_type: editing.value_type, description: editing.description ?? '' }}
          fields={[{ name: 'key', label: 'Khóa', required: true }, { name: 'value', label: 'Giá trị', required: true }, { name: 'value_type', label: 'Kiểu', type: 'select', required: true, options: types }, { name: 'description', label: 'Mô tả' }]} />
      )}
    </>
  );
}

interface AuditRow { id: number; action: string; entity_type: string | null; entity_id: string | null; ip_address: string | null; details: unknown; created_at: string; user_email: string | null }

export function AuditPage() {
  const { filters, page, setFilter, setPage } = useUrlFilters(['action', 'entity_type']);
  const q = usePagedQuery<AuditRow>('audit', '/audit-logs', filters, page);
  const [open, setOpen] = useState<number | null>(null);
  return (
    <>
      <PageHeader title="Nhật ký hoạt động" subtitle="Mọi thao tác ghi của quản trị viên" />
      <Card>
        <FilterBar values={filters} onChange={setFilter} defs={[{ name: 'action', label: 'Hành động', placeholder: 'ví dụ: user.lock' }, { name: 'entity_type', label: 'Đối tượng', placeholder: 'ví dụ: user' }]} />
        <DataTable rows={q.data?.items} loading={q.isLoading} error={q.error} onRetry={() => void q.refetch()} rowKey={(a) => a.id} onRowClick={(a) => setOpen(open === a.id ? null : a.id)}
          columns={[
            { header: 'Lúc', cell: (a) => formatDateTime(a.created_at) }, { header: 'Người thực hiện', cell: (a) => a.user_email ?? '—' }, { header: 'Hành động', cell: (a) => <span className="mono">{a.action}</span> },
            { header: 'Đối tượng', cell: (a) => `${a.entity_type ?? ''} ${a.entity_id ?? ''}` }, { header: 'IP', cell: (a) => a.ip_address ?? '—' },
            { header: 'Chi tiết', cell: (a) => (open === a.id ? <JsonView value={a.details} /> : <span className="muted small">bấm để xem</span>) },
          ]} />
        {q.data && <Pagination page={q.data.page} pageSize={q.data.page_size} total={q.data.total} onPage={setPage} />}
      </Card>
    </>
  );
}
