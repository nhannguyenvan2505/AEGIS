import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../../../core/api/client';
import { ApiError } from '../../../core/api/errors';
import { useAuth } from '../../../core/auth/AuthContext';
import { formatDateTime, parseJson } from '../../../core/utils/format';
import { DataTable, FilterBar, Pagination } from '../../../shared/data-table/DataTable';
import { ErrorState } from '../../../shared/feedback/Feedback';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { ActiveBadge } from '../../../shared/status/Badges';
import { Card, JsonView } from '../../../shared/ui/Card';
import { ConfirmDialog, FormDialog, type FormValues } from '../../../shared/ui/Dialogs';
import { useAction } from '../../../shared/hooks/useAction';
import { usePagedQuery } from '../../../shared/hooks/usePagedQuery';
import { useUrlFilters } from '../../../shared/hooks/useUrlFilters';

interface Model {
  id: number; model_type: string; version_name: string; algorithm: string; training_dataset: string | null; metrics_json: unknown;
  artifact_path: string; artifact_sha256: string | null; is_active: number | boolean; created_at: string;
}
interface Compare { models: Model[]; usage: { id: number; detections: number; avg_confidence: number }[] }

export default function ModelPage() {
  const { can } = useAuth();
  const { filters, page, setFilter, setPage } = useUrlFilters(['type']);
  const query = usePagedQuery<Model>('models', '/models', filters, page);
  const [registering, setRegistering] = useState(false);
  const [activating, setActivating] = useState<Model | null>(null);
  const [picked, setPicked] = useState<number[]>([]);
  const [pair, setPair] = useState<[number, number] | null>(null);

  const register = useAction((v: FormValues) => {
    const metrics = v.metrics ? parseJson<unknown>(String(v.metrics)) : undefined;
    if (v.metrics && metrics === null) throw new ApiError('invalid_json', 'Chỉ số (metrics) phải là JSON hợp lệ.', 422);
    return api('/models', { method: 'POST', body: { model_type: v.model_type, version_name: v.version_name, algorithm: v.algorithm, training_dataset: v.training_dataset || undefined,
      artifact_path: v.artifact_path, artifact_sha256: v.artifact_sha256 || undefined, metrics: metrics ?? undefined } });
  }, { invalidate: ['models'], success: 'Đã đăng ký phiên bản mô hình.' });
  const activate = useAction((id: number) => api(`/models/${id}/activate`, { method: 'POST' }), { invalidate: ['models'], success: 'Đã kích hoạt phiên bản.' });
  const compare = useQuery({ queryKey: ['models', 'compare', pair], enabled: pair !== null, queryFn: ({ signal }) => api<Compare>('/models/compare', { params: { a: pair![0], b: pair![1] }, signal }) });
  const toggle = (id: number) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id].slice(-2)));

  return (
    <>
      <PageHeader title="Mô hình AI" subtitle="Các phiên bản mô hình nhận diện bệnh và dự báo rủi ro"
        actions={<>
          <button className="btn secondary" disabled={picked.length !== 2} onClick={() => setPair([picked[0], picked[1]])}>So sánh 2 phiên bản đã chọn</button>
          {can('admin') && <button className="btn" onClick={() => setRegistering(true)}>Đăng ký phiên bản</button>}
        </>} />
      <Card>
        <FilterBar values={filters} onChange={setFilter} defs={[{ name: 'type', label: 'Loại', type: 'select', options: [{ value: 'yolo_detection', label: 'Nhận diện (YOLO)' }, { value: 'risk_prediction', label: 'Dự báo rủi ro' }] }]} />
        <DataTable rows={query.data?.items} loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} rowKey={(m) => m.id}
          empty="Chưa có phiên bản mô hình nào được đăng ký."
          columns={[
            { header: 'So sánh', cell: (m) => <input type="checkbox" aria-label={`Chọn ${m.version_name} để so sánh`} checked={picked.includes(m.id)} onChange={() => toggle(m.id)} /> },
            { header: 'Phiên bản', cell: (m) => <><strong>{m.version_name}</strong><div className="small muted">{m.model_type}</div></> }, { header: 'Thuật toán', cell: (m) => m.algorithm },
            { header: 'SHA-256', cell: (m) => <span className="mono">{m.artifact_sha256?.slice(0, 12) ?? '—'}</span> }, { header: 'Đang dùng', cell: (m) => <ActiveBadge value={m.is_active} /> },
            { header: 'Tạo lúc', cell: (m) => formatDateTime(m.created_at) },
            { header: '', cell: (m) => can('admin') && !m.is_active && <button className="btn secondary small" onClick={() => setActivating(m)}>Kích hoạt</button> },
          ]} />
        {query.data && <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPage={setPage} />}
      </Card>
      {pair && (
        <Card title="So sánh phiên bản" actions={<button className="btn ghost small" onClick={() => setPair(null)}>Đóng</button>}>
          {compare.isError ? <ErrorState error={compare.error} /> : (
            <div className="grid-2">{compare.data?.models.map((m) => {
              const u = compare.data!.usage.find((x) => x.id === m.id);
              return (
                <div key={m.id}><h3>{m.version_name}</h3>
                  <p className="small muted">Đã dùng cho {u?.detections ?? 0} chẩn đoán · tin cậy TB {u ? (u.avg_confidence * 100).toFixed(1) : '—'}%</p>
                  <JsonView value={m.metrics_json} /></div>
              );
            })}</div>
          )}
        </Card>
      )}
      {registering && (
        <FormDialog open title="Đăng ký phiên bản mô hình" submitLabel="Đăng ký" onClose={() => setRegistering(false)} onSubmit={register} initial={{ model_type: 'yolo_detection' }}
          fields={[
            { name: 'model_type', label: 'Loại', type: 'select', required: true, options: [{ value: 'yolo_detection', label: 'Nhận diện (YOLO)' }, { value: 'risk_prediction', label: 'Dự báo rủi ro' }] },
            { name: 'version_name', label: 'Tên phiên bản', required: true }, { name: 'algorithm', label: 'Thuật toán', required: true }, { name: 'training_dataset', label: 'Tập huấn luyện' },
            { name: 'artifact_path', label: 'Đường dẫn artifact trên máy chủ', required: true, help: 'Chỉ lưu metadata; tệp phải đã nằm sẵn trên máy chủ.' },
            { name: 'artifact_sha256', label: 'SHA-256 (64 ký tự hex thường)' }, { name: 'metrics', label: 'Chỉ số (JSON)', type: 'textarea', placeholder: '{"mAP50": 0.0}' },
          ]} />
      )}
      {activating && (
        <ConfirmDialog open danger confirmLabel="Kích hoạt" title={`Kích hoạt ${activating.version_name}`} onClose={() => setActivating(null)} onConfirm={() => activate(activating.id)}
          message="Chỉ đổi cờ trong cơ sở dữ liệu (mỗi loại chỉ có một bản đang dùng). Dịch vụ AI vẫn phải được triển khai với đúng artifact tương ứng." />
      )}
    </>
  );
}
