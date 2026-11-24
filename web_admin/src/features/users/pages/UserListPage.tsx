import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { formatDateTime } from '../../../core/utils/format';
import { DataTable, FilterBar, Pagination } from '../../../shared/data-table/DataTable';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { RoleBadge, UserStatusBadge } from '../../../shared/status/Badges';
import { Card } from '../../../shared/ui/Card';
import { FormDialog, type FormValues } from '../../../shared/ui/Dialogs';
import { useAction } from '../../../shared/hooks/useAction';
import { usePagedQuery } from '../../../shared/hooks/usePagedQuery';
import { useUrlFilters } from '../../../shared/hooks/useUrlFilters';
import { createUser } from '../api';
import type { UserRow } from '../types';

const KEYS = ['q', 'role', 'status'] as const;

export default function UserListPage() {
  const navigate = useNavigate();
  const { filters, page, setFilter, setPage } = useUrlFilters(KEYS);
  const query = usePagedQuery<UserRow>('users', '/users', filters, page);
  const [creating, setCreating] = useState(false);
  const create = useAction((v: FormValues) => createUser({ ...v, full_name: v.full_name || undefined, phone: v.phone || undefined }),
    { invalidate: ['users', 'stats'], success: 'Đã tạo người dùng.' });

  return (
    <>
      <PageHeader title="Người dùng" subtitle="Quản lý tài khoản và phân quyền"
        actions={<button className="btn" onClick={() => setCreating(true)}>Tạo người dùng</button>} />
      <Card>
        <FilterBar values={filters} onChange={setFilter} defs={[
          { name: 'q', label: 'Tìm kiếm', placeholder: 'Email hoặc họ tên' },
          { name: 'role', label: 'Vai trò', type: 'select', options: ['farmer', 'admin'].map((v) => ({ value: v, label: v })) },
          { name: 'status', label: 'Trạng thái', type: 'select', options: [{ value: 'active', label: 'Hoạt động' }, { value: 'inactive', label: 'Vô hiệu hóa' }, { value: 'locked', label: 'Bị khóa' }] },
        ]} />
        <DataTable rows={query.data?.items} loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()}
          rowKey={(u) => u.id} onRowClick={(u) => navigate(`/users/${u.id}`)}
          columns={[
            { header: 'Email', cell: (u) => <strong>{u.email}</strong> },
            { header: 'Họ tên', cell: (u) => u.full_name ?? '—' },
            { header: 'Vai trò', cell: (u) => <RoleBadge value={u.role} /> },
            { header: 'Trạng thái', cell: (u) => <UserStatusBadge value={u.status} /> },
            { header: 'Nông trại', cell: (u) => u.farm_count },
            { header: 'Đăng nhập cuối', cell: (u) => formatDateTime(u.last_login_at) },
          ]} />
        {query.data && <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPage={setPage} />}
      </Card>
      {creating && (
        <FormDialog open title="Tạo người dùng" submitLabel="Tạo" onClose={() => setCreating(false)} onSubmit={create}
          initial={{ role: 'farmer' }}
          fields={[
            { name: 'email', label: 'Email', type: 'text', required: true },
            { name: 'password', label: 'Mật khẩu (12–128 ký tự)', type: 'password', required: true },
            { name: 'full_name', label: 'Họ tên' },
            { name: 'phone', label: 'Số điện thoại' },
            { name: 'role', label: 'Vai trò', type: 'select', required: true, options: ['farmer', 'admin'].map((v) => ({ value: v, label: v })) },
          ]} />
      )}
    </>
  );
}
