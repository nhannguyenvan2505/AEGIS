import * as Tabs from '@radix-ui/react-tabs';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../../../core/api/client';
import { useAuth } from '../../../core/auth/AuthContext';
import { DataTable } from '../../../shared/data-table/DataTable';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { ActiveBadge } from '../../../shared/status/Badges';
import { Card } from '../../../shared/ui/Card';
import { ConfirmDialog, FormDialog, type FieldDef, type FormValues } from '../../../shared/ui/Dialogs';
import { useAction } from '../../../shared/hooks/useAction';

interface Disease { id: number; disease_name: string; crop_type: string; scientific_name: string | null; description: string | null; active: number | boolean }
interface Recommendation { id: number; disease_id: number; disease_name: string; title: string; recommendation_text: string; precautions: string | null; source_reference: string | null; active: number | boolean }

const useList = <T,>(key: string, path: string) => useQuery({ queryKey: [key, 'list'], queryFn: ({ signal }) => api<{ items: T[] }>(path, { signal }) });
const blank = (v: string | null | undefined) => v || undefined;

function DiseasesTab() {
  const { can } = useAuth();
  const q = useList<Disease>('diseases', '/diseases');
  const [editing, setEditing] = useState<Disease | 'new' | null>(null);
  const [deleting, setDeleting] = useState<Disease | null>(null);
  const save = useAction((v: FormValues) => {
    const body = { disease_name: v.disease_name, crop_type: v.crop_type, scientific_name: blank(v.scientific_name as string), description: blank(v.description as string), active: Boolean(v.active) };
    return editing && editing !== 'new' ? api(`/diseases/${editing.id}`, { method: 'PUT', body }) : api('/diseases', { method: 'POST', body });
  }, { invalidate: ['diseases', 'recommendations'], success: 'Đã lưu.' });
  const remove = useAction((id: number) => api(`/diseases/${id}`, { method: 'DELETE' }), { invalidate: ['diseases', 'recommendations'], success: 'Đã xóa bệnh.' });
  const fields: FieldDef[] = [
    { name: 'disease_name', label: 'Tên bệnh (mã)', required: true, help: 'Ví dụ: rice_blast' }, { name: 'crop_type', label: 'Cây trồng', required: true },
    { name: 'scientific_name', label: 'Tên khoa học' }, { name: 'description', label: 'Mô tả', type: 'textarea' }, { name: 'active', label: 'Đang dùng', type: 'checkbox' },
  ];
  return (
    <>
      <div className="row" style={{ marginBottom: 8 }}><div className="spacer" />{<button className="btn" onClick={() => setEditing('new')}>Thêm bệnh</button>}</div>
      <DataTable rows={q.data?.items} loading={q.isLoading} error={q.error} onRetry={() => void q.refetch()} rowKey={(d) => d.id}
        empty="Chưa có bệnh nào. Chạy backend/database/mysql/admin/001_admin_additions.sql để nạp 3 bệnh lúa, hoặc thêm tay."
        columns={[
          { header: 'Tên', cell: (d) => <strong>{d.disease_name}</strong> }, { header: 'Cây trồng', cell: (d) => d.crop_type }, { header: 'Tên khoa học', cell: (d) => d.scientific_name ?? '—' },
          { header: 'Trạng thái', cell: (d) => <ActiveBadge value={d.active} /> },
          { header: '', cell: (d) => <div className="row"><button className="btn secondary small" onClick={() => setEditing(d)}>Sửa</button>{can('admin') && <button className="btn danger small" onClick={() => setDeleting(d)}>Xóa</button>}</div> },
        ]} />
      {editing && <FormDialog open title={editing === 'new' ? 'Thêm bệnh' : 'Sửa bệnh'} fields={fields} onClose={() => setEditing(null)} onSubmit={save}
        initial={editing === 'new' ? { active: true } : { disease_name: editing.disease_name, crop_type: editing.crop_type, scientific_name: editing.scientific_name ?? '', description: editing.description ?? '', active: Boolean(editing.active) }} />}
      {deleting && <ConfirmDialog open danger confirmLabel="Xóa" title="Xóa bệnh" onClose={() => setDeleting(null)} message={`Xóa "${deleting.disease_name}" sẽ xóa cả khuyến nghị liên quan. Không xóa được nếu đang được chẩn đoán hoặc dự báo tham chiếu.`} onConfirm={() => remove(deleting.id)} />}
    </>
  );
}

function RecommendationsTab() {
  const q = useList<Recommendation>('recommendations', '/recommendations');
  const diseases = useList<Disease>('diseases', '/diseases');
  const [editing, setEditing] = useState<Recommendation | 'new' | null>(null);
  const [deleting, setDeleting] = useState<Recommendation | null>(null);
  const save = useAction((v: FormValues) => {
    const body = { disease_id: Number(v.disease_id), title: v.title, recommendation_text: v.recommendation_text, precautions: blank(v.precautions as string), source_reference: blank(v.source_reference as string), active: Boolean(v.active) };
    return editing && editing !== 'new' ? api(`/recommendations/${editing.id}`, { method: 'PUT', body }) : api('/recommendations', { method: 'POST', body });
  }, { invalidate: ['recommendations'], success: 'Đã lưu.' });
  const remove = useAction((id: number) => api(`/recommendations/${id}`, { method: 'DELETE' }), { invalidate: ['recommendations'], success: 'Đã xóa khuyến nghị.' });
  const fields: FieldDef[] = [
    { name: 'disease_id', label: 'Bệnh', type: 'select', required: true, options: (diseases.data?.items ?? []).map((d) => ({ value: String(d.id), label: d.disease_name })) },
    { name: 'title', label: 'Tiêu đề', required: true }, { name: 'recommendation_text', label: 'Nội dung khuyến nghị', type: 'textarea', required: true },
    { name: 'precautions', label: 'Lưu ý', type: 'textarea' }, { name: 'source_reference', label: 'Nguồn tham khảo' }, { name: 'active', label: 'Đang dùng', type: 'checkbox' },
  ];
  return (
    <>
      <div className="row" style={{ marginBottom: 8 }}><div className="spacer" /><button className="btn" onClick={() => setEditing('new')} disabled={!diseases.data?.items.length} title={diseases.data?.items.length ? undefined : 'Cần có ít nhất một bệnh'}>Thêm khuyến nghị</button></div>
      <DataTable rows={q.data?.items} loading={q.isLoading} error={q.error} onRetry={() => void q.refetch()} rowKey={(r) => r.id} empty="Chưa có khuyến nghị."
        columns={[
          { header: 'Bệnh', cell: (r) => r.disease_name }, { header: 'Tiêu đề', cell: (r) => <><strong>{r.title}</strong><div className="small muted">{r.recommendation_text.slice(0, 120)}{r.recommendation_text.length > 120 ? '…' : ''}</div></> },
          { header: 'Nguồn', cell: (r) => r.source_reference ?? '—' }, { header: 'Trạng thái', cell: (r) => <ActiveBadge value={r.active} /> },
          { header: '', cell: (r) => <div className="row"><button className="btn secondary small" onClick={() => setEditing(r)}>Sửa</button><button className="btn danger small" onClick={() => setDeleting(r)}>Xóa</button></div> },
        ]} />
      {editing && <FormDialog open title={editing === 'new' ? 'Thêm khuyến nghị' : 'Sửa khuyến nghị'} fields={fields} onClose={() => setEditing(null)} onSubmit={save}
        initial={editing === 'new' ? { active: true, disease_id: String(diseases.data?.items[0]?.id ?? '') } : { disease_id: String(editing.disease_id), title: editing.title, recommendation_text: editing.recommendation_text, precautions: editing.precautions ?? '', source_reference: editing.source_reference ?? '', active: Boolean(editing.active) }} />}
      {deleting && <ConfirmDialog open danger confirmLabel="Xóa" title="Xóa khuyến nghị" message={`Xóa "${deleting.title}"?`} onClose={() => setDeleting(null)} onConfirm={() => remove(deleting.id)} />}
    </>
  );
}

export default function KnowledgePage() {
  return (
    <>
      <PageHeader title="Bệnh & khuyến nghị điều trị" subtitle="Danh mục bệnh và nội dung khuyến nghị hiển thị cho nông dân" />
      <Card>
        <Tabs.Root defaultValue="diseases">
          <Tabs.List className="tabs"><Tabs.Trigger value="diseases">Bệnh</Tabs.Trigger><Tabs.Trigger value="recommendations">Khuyến nghị</Tabs.Trigger></Tabs.List>
          <Tabs.Content value="diseases"><DiseasesTab /></Tabs.Content>
          <Tabs.Content value="recommendations"><RecommendationsTab /></Tabs.Content>
        </Tabs.Root>
      </Card>
    </>
  );
}
