import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../../../core/api/client';
import { formatDateTime, formatPercent, parseJson } from '../../../core/utils/format';
import { DataTable, FilterBar, Pagination } from '../../../shared/data-table/DataTable';
import { ErrorState, LoadingState } from '../../../shared/feedback/Feedback';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { DISEASE_LABEL, DiseaseBadge } from '../../../shared/status/Badges';
import { Card, KeyValue } from '../../../shared/ui/Card';
import { UserCell } from '../../../shared/ui/UserCell';
import { usePagedQuery } from '../../../shared/hooks/usePagedQuery';
import { useUrlFilters } from '../../../shared/hooks/useUrlFilters';
import { ImageWithBBox } from '../components/ImageWithBBox';
import type { BBox, DetectionDetail, DetectionRow } from '../types';

const KEYS = ['user', 'disease', 'min_confidence', 'max_confidence'] as const;
const CLASSES = [['0', 'rice_blast'], ['1', 'brown_spot'], ['2', 'sheath_blight']];

export function DetectionListPage() {
  const navigate = useNavigate();
  const { filters, page, setFilter, setPage } = useUrlFilters(KEYS);
  const query = usePagedQuery<DetectionRow>('detections', '/detections', filters, page);
  return (
    <>
      <PageHeader title="Chẩn đoán bệnh" subtitle="Kết quả AI tự dự đoán từ ảnh khách hàng tải lên (chỉ xem)" />
      <Card>
        <FilterBar values={filters} onChange={setFilter} defs={[
          { name: 'user', label: 'Người dùng', placeholder: 'Tên hoặc email' },
          { name: 'disease', label: 'Bệnh', type: 'select', options: CLASSES.map(([, v]) => ({ value: v, label: DISEASE_LABEL[v] })) },
          { name: 'min_confidence', label: 'Tin cậy từ (0–1)', placeholder: '0.0' }, { name: 'max_confidence', label: 'Đến (0–1)', placeholder: '1.0' },
        ]} />
        <DataTable rows={query.data?.items} loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()}
          rowKey={(d) => d.id} onRowClick={(d) => navigate(`/detections/${d.id}`)}
          columns={[
            { header: 'Bệnh', cell: (d) => <DiseaseBadge value={d.disease} /> }, { header: 'Tin cậy', cell: (d) => formatPercent(d.confidence) },
            { header: 'Người dùng', cell: (d) => <UserCell name={d.user_name} email={d.user_email} /> },
            { header: 'Mô hình', cell: (d) => <span className="mono">{d.model_version}</span> }, { header: 'Lúc', cell: (d) => formatDateTime(d.created_at) },
          ]} />
        {query.data && <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPage={setPage} />}
      </Card>
    </>
  );
}

export function DetectionDetailPage() {
  const { id = '' } = useParams();
  const q = useQuery({ queryKey: ['detections', 'detail', id], queryFn: ({ signal }) => api<{ detection: DetectionDetail }>(`/detections/${id}`, { signal }) });
  if (q.isLoading) return <LoadingState />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const d = q.data!.detection;
  const bbox = parseJson<BBox>(d.bbox);
  return (
    <>
      <PageHeader title={`Chẩn đoán: ${DISEASE_LABEL[d.disease] ?? d.disease}`} crumbs={[{ label: 'Chẩn đoán', to: '/detections' }, { label: id.slice(0, 8) }]} />
      <div className="grid-2">
        <Card title="Ảnh và khung phát hiện">
          <ImageWithBBox path={d.image_url} width={d.image_width} height={d.image_height} bbox={bbox} label={`${DISEASE_LABEL[d.disease] ?? d.disease} ${formatPercent(d.confidence)}`} />
        </Card>
        <Card title="Kết quả">
          <KeyValue rows={[
            ['Bệnh', <DiseaseBadge value={d.disease} />], ['Độ tin cậy', <><div className="bar" aria-hidden><i style={{ width: `${d.confidence * 100}%` }} /></div>{formatPercent(d.confidence)}</>],
            ['Người dùng', <Link to={`/users/${d.user_id}`}>{d.user_email}</Link>],
            ['Mô hình', <span className="mono">{d.model_version}</span>], ['SHA mô hình', <span className="mono">{d.model_sha256.slice(0, 16)}…</span>],
            ['Thời gian AI (ms)', d.ai_processing_ms], ['Kích thước ảnh', `${d.image_width}×${d.image_height} · ${d.orientation}`], ['Mã yêu cầu', <span className="mono">{d.request_id}</span>], ['Lúc', formatDateTime(d.created_at)],
          ]} />
        </Card>
      </div>
    </>
  );
}
