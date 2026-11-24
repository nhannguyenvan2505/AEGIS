import { useState } from 'react';
import { api } from '../../../core/api/client';
import { useAuth } from '../../../core/auth/AuthContext';
import { formatDateTime } from '../../../core/utils/format';
import { DataTable, FilterBar, Pagination } from '../../../shared/data-table/DataTable';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { ActiveBadge, SeverityBadge } from '../../../shared/status/Badges';
import { Card } from '../../../shared/ui/Card';
import { ConfirmDialog, FormDialog, type FieldDef, type FormValues } from '../../../shared/ui/Dialogs';
import { useAction } from '../../../shared/hooks/useAction';
import { usePagedQuery } from '../../../shared/hooks/usePagedQuery';
import { useUrlFilters } from '../../../shared/hooks/useUrlFilters';

interface Threshold {
  id: number; metric: string; operator: string; threshold_value: number; threshold_value_2: number | null; severity: string; is_active: number | boolean;
  updated_at: string; farm_id: string | null; farm_name: string | null; plot_id: string | null; plot_name: string | null;
}
const METRICS = ['temperature', 'humidity', 'soil_moisture', 'soil_ph', 'risk_probability', 'confidence'];
const OPS = [['gt', '>'], ['gte', '≥'], ['lt', '<'], ['lte', '≤'], ['between', 'trong khoảng']];
const opText = (t: Threshold) => (t.operator === 'between' ? `${t.threshold_value} – ${t.threshold_value_2}` : `${OPS.find(([k]) => k === t.operator)?.[1]} ${t.threshold_value}`);

const FIELDS: FieldDef[] = [
  { name: 'metric', label: 'Chỉ số', type: 'select', required: true, options: METRICS.map((v) => ({ value: v, label: v })) },
  { name: 'operator', label: 'Toán tử', type: 'select', required: true, options: OPS.map(([value, label]) => ({ value, label })) },
  { name: 'threshold_value', label: 'Giá trị', type: 'number', required: true },
  { name: 'threshold_value_2', label: 'Giá trị 2 (chỉ khi chọn "trong khoảng")', type: 'number' },
  { name: 'severity', label: 'Mức độ', type: 'select', required: true, options: ['info', 'warning', 'high', 'critical'].map((v) => ({ value: v, label: v })) },
  { name: 'farm_id', label: 'ID nông trại (để trống = toàn hệ thống)' }, { name: 'plot_id', label: 'ID ruộng (ưu tiên hơn nông trại)' },
  { name: 'is_active', label: 'Đang bật', type: 'checkbox' },
];

/** Chuyển giá trị form thành body: chuỗi rỗng bỏ qua, số chuyển sang number. */
function toBody(v: FormValues) {
  const num = (x: string | boolean | undefined) => (x === '' || x === undefined ? undefined : Number(x));
  return {
    metric: v.metric, operator: v.operator, severity: v.severity, threshold_value: num(v.threshold_value),
    threshold_value_2: v.operator === 'between' ? num(v.threshold_value_2) : undefined,
    farm_id: v.farm_id || undefined, plot_id: v.plot_id || undefined, is_active: Boolean(v.is_active),
  };
}

export default function ThresholdPage() {
  const { can } = useAuth();
  const { filters, page, setFilter, setPage } = useUrlFilters(['metric']);
  const query = usePagedQuery<Threshold>('thresholds', '/thresholds', filters, page);
  const [editing, setEditing] = useState<Threshold | 'new' | null>(null);
  const [deleting, setDeleting] = useState<Threshold | null>(null);
  const save = useAction((v: FormValues) => (editing && editing !== 'new'
    ? api(`/thresholds/${editing.id}`, { method: 'PUT', body: toBody(v) }) : api('/thresholds', { method: 'POST', body: toBody(v) })), { invalidate: ['thresholds'], success: 'Đã lưu ngưỡng.' });
  const remove = useAction((id: number) => api(`/thresholds/${id}`, { method: 'DELETE' }), { invalidate: ['thresholds'], success: 'Đã xóa ngưỡng.' });
  const dryRun = async (v: FormValues) => {
    const r = await api<{ matches: number; supported: boolean; note?: string }>('/thresholds/dry-run', { method: 'POST', body: toBody(v) });
    return r.supported ? `Có ${r.matches} bản ghi trong 7 ngày gần đây sẽ vượt ngưỡng này.` : (r.note ?? 'Chưa hỗ trợ chạy thử chỉ số này.');
  };

  const initial = (t: Threshold | 'new'): FormValues => (t === 'new'
    ? { metric: 'confidence', operator: 'lt', severity: 'warning', is_active: true, threshold_value: '', threshold_value_2: '', farm_id: '', plot_id: '' }
    : { metric: t.metric, operator: t.operator, severity: t.severity, is_active: Boolean(t.is_active), threshold_value: String(t.threshold_value), threshold_value_2: t.threshold_value_2 === null ? '' : String(t.threshold_value_2), farm_id: t.farm_id ?? '', plot_id: t.plot_id ?? '' });

  return (
    <>
      <PageHeader title="Ngưỡng cảnh báo" subtitle="Điều kiện sinh cảnh báo cho toàn hệ thống, nông trại hoặc ruộng"
        actions={can('admin') && <button className="btn" onClick={() => setEditing('new')}>Thêm ngưỡng</button>} />
      <Card>
        <FilterBar values={filters} onChange={setFilter} defs={[{ name: 'metric', label: 'Chỉ số', type: 'select', options: METRICS.map((v) => ({ value: v, label: v })) }]} />
        <DataTable rows={query.data?.items} loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} rowKey={(t) => t.id}
          columns={[
            { header: 'Chỉ số', cell: (t) => <strong>{t.metric}</strong> }, { header: 'Điều kiện', cell: (t) => opText(t) }, { header: 'Mức độ', cell: (t) => <SeverityBadge value={t.severity} /> },
            { header: 'Phạm vi', cell: (t) => t.plot_name ?? t.farm_name ?? 'Toàn hệ thống' }, { header: 'Trạng thái', cell: (t) => <ActiveBadge value={t.is_active} /> },
            { header: 'Cập nhật', cell: (t) => formatDateTime(t.updated_at) },
            { header: '', cell: (t) => can('admin') && <div className="row"><button className="btn secondary small" onClick={() => setEditing(t)}>Sửa</button><button className="btn danger small" onClick={() => setDeleting(t)}>Xóa</button></div> },
          ]} />
        {query.data && <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPage={setPage} />}
      </Card>
      {editing && (
        <FormDialog open title={editing === 'new' ? 'Thêm ngưỡng' : 'Sửa ngưỡng'} fields={FIELDS} initial={initial(editing)} onClose={() => setEditing(null)} onSubmit={save}
          submitLabel="Lưu" extraAction={{ label: 'Chạy thử', run: dryRun }} />
      )}
      {deleting && <ConfirmDialog open danger confirmLabel="Xóa" title="Xóa ngưỡng" message={`Xóa ngưỡng ${deleting.metric} ${opText(deleting)}?`} onClose={() => setDeleting(null)} onConfirm={() => remove(deleting.id)} />}
    </>
  );
}
