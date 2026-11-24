import { useState } from 'react';
import { api } from '../../../core/api/client';
import { useAuth } from '../../../core/auth/AuthContext';
import { formatDateTime } from '../../../core/utils/format';
import { DataTable, FilterBar, Pagination } from '../../../shared/data-table/DataTable';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { AlertStatusBadge, DeliveryBadge, SeverityBadge } from '../../../shared/status/Badges';
import { Card } from '../../../shared/ui/Card';
import { UserCell } from '../../../shared/ui/UserCell';
import { ConfirmDialog } from '../../../shared/ui/Dialogs';
import { useAction } from '../../../shared/hooks/useAction';
import { usePagedQuery } from '../../../shared/hooks/usePagedQuery';
import { useUrlFilters } from '../../../shared/hooks/useUrlFilters';
import * as Tabs from '@radix-ui/react-tabs';

interface AlertRow { id: number; alert_type: string; severity: string; title: string; message: string; status: 'open' | 'acknowledged' | 'resolved'; generated_at: string; plot_name: string; owner_email: string; owner_name?: string | null }
interface NotificationRow { id: number; channel: string; title: string; message: string; delivery_status: 'pending' | 'sent' | 'failed'; is_read: boolean; created_at: string; user_email: string }

// Khớp bảng chuyển trạng thái của backend (features/alerts/routes.py).
const NEXT: Record<AlertRow['status'], { to: AlertRow['status']; label: string }[]> = {
  open: [{ to: 'acknowledged', label: 'Ghi nhận' }, { to: 'resolved', label: 'Đã xử lý' }],
  acknowledged: [{ to: 'resolved', label: 'Đã xử lý' }, { to: 'open', label: 'Mở lại' }],
  resolved: [{ to: 'open', label: 'Mở lại' }],
};
const TYPES = [['environment_anomaly', 'Môi trường bất thường'], ['disease_detected', 'Phát hiện bệnh'], ['high_risk', 'Rủi ro cao'], ['device_offline', 'Thiết bị mất kết nối']];

function AlertsTab() {
  const { can } = useAuth();
  const { filters, page, setFilter, setPage } = useUrlFilters(['user', 'type', 'severity', 'status']);
  const query = usePagedQuery<AlertRow>('alerts', '/alerts', filters, page);
  const [target, setTarget] = useState<{ alert: AlertRow; to: AlertRow['status']; label: string } | null>(null);
  const change = useAction((v: { id: number; to: string }) => api(`/alerts/${v.id}/status`, { method: 'PUT', body: { status: v.to } }), { invalidate: ['alerts', 'stats'], success: 'Đã cập nhật cảnh báo.' });
  return (
    <>
      <FilterBar values={filters} onChange={setFilter} defs={[
        { name: 'user', label: 'Người dùng', placeholder: 'Tên hoặc email' },
        { name: 'type', label: 'Loại', type: 'select', options: TYPES.map(([value, label]) => ({ value, label })) },
        { name: 'severity', label: 'Mức độ', type: 'select', options: ['info', 'warning', 'high', 'critical'].map((v) => ({ value: v, label: v })) },
        { name: 'status', label: 'Trạng thái', type: 'select', options: ['open', 'acknowledged', 'resolved'].map((v) => ({ value: v, label: v })) },
      ]} />
      <DataTable rows={query.data?.items} loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} rowKey={(a) => a.id}
        columns={[
          { header: 'Mức độ', cell: (a) => <SeverityBadge value={a.severity} /> },
          { header: 'Cảnh báo', cell: (a) => <><strong>{a.title}</strong><div className="small muted">{a.message}</div></> },
          { header: 'Ruộng', cell: (a) => <>{a.plot_name}<div className="small muted"><UserCell name={a.owner_name} email={a.owner_email} /></div></> },
          { header: 'Trạng thái', cell: (a) => <AlertStatusBadge value={a.status} /> }, { header: 'Lúc', cell: (a) => formatDateTime(a.generated_at) },
          { header: '', cell: (a) => can('admin') && <div className="row">{NEXT[a.status].map((n) => <button key={n.to} className="btn secondary small" onClick={() => setTarget({ alert: a, ...n })}>{n.label}</button>)}</div> },
        ]} />
      {query.data && <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPage={setPage} />}
      {target && <ConfirmDialog open title="Đổi trạng thái cảnh báo" message={`Chuyển "${target.alert.title}" sang: ${target.label}?`} onClose={() => setTarget(null)} onConfirm={() => change({ id: target.alert.id, to: target.to })} />}
    </>
  );
}

function NotificationsTab() {
  const { can } = useAuth();
  const { filters, page, setFilter, setPage } = useUrlFilters(['delivery_status']);
  const query = usePagedQuery<NotificationRow>('notifications', '/notifications', filters, page);
  const resend = useAction((id: number) => api(`/notifications/${id}/resend`, { method: 'POST' }), { invalidate: ['notifications'], success: 'Đã đưa vào hàng đợi gửi lại.' });
  return (
    <>
      <FilterBar values={filters} onChange={setFilter} defs={[{ name: 'delivery_status', label: 'Gửi', type: 'select', options: ['pending', 'sent', 'failed'].map((v) => ({ value: v, label: v })) }]} />
      <DataTable rows={query.data?.items} loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} rowKey={(n) => n.id}
        columns={[
          { header: 'Thông báo', cell: (n) => <><strong>{n.title}</strong><div className="small muted">{n.message}</div></> }, { header: 'Người nhận', cell: (n) => n.user_email },
          { header: 'Kênh', cell: (n) => n.channel }, { header: 'Gửi', cell: (n) => <DeliveryBadge value={n.delivery_status} /> }, { header: 'Đã đọc', cell: (n) => (n.is_read ? 'Có' : 'Chưa') },
          { header: 'Lúc', cell: (n) => formatDateTime(n.created_at) },
          { header: '', cell: (n) => can('admin') && n.delivery_status === 'failed' && <button className="btn secondary small" onClick={() => void resend(n.id)}>Gửi lại</button> },
        ]} />
      {query.data && <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPage={setPage} />}
    </>
  );
}

export default function AlertsPage() {
  return (
    <>
      <PageHeader title="Cảnh báo & thông báo" subtitle="Cảnh báo hệ thống sinh ra từ thiết bị, chẩn đoán và dự báo" />
      <Card>
        <Tabs.Root defaultValue="alerts">
          <Tabs.List className="tabs"><Tabs.Trigger value="alerts">Cảnh báo</Tabs.Trigger><Tabs.Trigger value="notifications">Thông báo</Tabs.Trigger></Tabs.List>
          <Tabs.Content value="alerts"><AlertsTab /></Tabs.Content>
          <Tabs.Content value="notifications"><NotificationsTab /></Tabs.Content>
        </Tabs.Root>
      </Card>
    </>
  );
}
