import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../../../core/auth/AuthContext';
import { formatDateTime } from '../../../core/utils/format';
import { ErrorState, LoadingState } from '../../../shared/feedback/Feedback';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { RoleBadge, UserStatusBadge } from '../../../shared/status/Badges';
import { Card, KeyValue } from '../../../shared/ui/Card';
import { ConfirmDialog, FormDialog, Modal, type FormValues } from '../../../shared/ui/Dialogs';
import { useAction } from '../../../shared/hooks/useAction';
import { deactivateUser, getUser, updateUser, userAction } from '../api';

type Pending = 'lock' | 'unlock' | 'revoke-sessions' | 'reset-password' | 'deactivate' | 'edit' | null;

export default function UserDetailPage() {
  const { id = '' } = useParams();
  const { user: me } = useAuth();
  const navigate = useNavigate();
  const query = useQuery({ queryKey: ['users', 'detail', id], queryFn: ({ signal }) => getUser(id, signal) });
  const [pending, setPending] = useState<Pending>(null);
  const [token, setToken] = useState<string | null>(null);
  const keys = ['users', 'stats'];
  const act = useAction((a: 'lock' | 'unlock' | 'revoke-sessions' | 'reset-password') => userAction(id, a), { invalidate: keys, success: 'Đã thực hiện.' });
  const deactivate = useAction(() => deactivateUser(id), { invalidate: keys, success: 'Đã vô hiệu hóa người dùng.' });
  const edit = useAction((v: FormValues) => updateUser(id, { full_name: v.full_name, phone: v.phone, role: v.role }), { invalidate: keys, success: 'Đã cập nhật.' });

  if (query.isLoading) return <LoadingState />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  const { user, farms, recent_analyses, activity } = query.data!;
  const isSelf = me?.id === user.id;
  const close = () => setPending(null);

  const simple = (a: 'lock' | 'unlock' | 'revoke-sessions') => async () => { await act(a); };

  return (
    <>
      <PageHeader title={user.email} crumbs={[{ label: 'Người dùng', to: '/users' }, { label: user.email }]}
        actions={<>
          <button className="btn secondary" onClick={() => setPending('edit')}>Sửa</button>
          {user.status === 'locked' || user.status === 'inactive'
            ? <button className="btn secondary" onClick={() => setPending('unlock')}>Mở khóa</button>
            : <button className="btn secondary" disabled={isSelf} title={isSelf ? 'Không thể tự khóa chính mình' : undefined} onClick={() => setPending('lock')}>Khóa</button>}
          <button className="btn secondary" onClick={() => setPending('revoke-sessions')}>Buộc đăng xuất</button>
          <button className="btn secondary" onClick={() => setPending('reset-password')}>Đặt lại mật khẩu</button>
          <button className="btn danger" disabled={isSelf} onClick={() => setPending('deactivate')}>Vô hiệu hóa</button>
        </>} />
      <Card title="Thông tin">
        <KeyValue rows={[
          ['Họ tên', user.full_name], ['Số điện thoại', user.phone], ['Vai trò', <RoleBadge value={user.role} />],
          ['Trạng thái', <UserStatusBadge value={user.status} />], ['Đăng nhập cuối', formatDateTime(user.last_login_at)], ['Tạo lúc', formatDateTime(user.created_at)],
        ]} />
      </Card>
      <div className="grid-2">
        <Card title={`Nông trại (${farms.length})`}>
          {farms.length === 0 ? <span className="muted">Chưa có nông trại.</span> : <ul>{farms.map((f) => <li key={f.id}><Link to={`/farms/${f.id}`}>{f.name}</Link> <span className="muted">{f.address}</span></li>)}</ul>}
        </Card>
        <Card title="Chẩn đoán gần đây">
          {recent_analyses.length === 0 ? <span className="muted">Chưa có.</span> : <ul>{recent_analyses.map((a) => <li key={a.id}>{formatDateTime(a.created_at)} · {a.status} <span className="muted mono">{a.model_version}</span></li>)}</ul>}
        </Card>
      </div>
      <Card title="Hoạt động của người này (nhật ký quản trị)">
        {activity.length === 0 ? <span className="muted">Không có.</span> : <ul>{activity.map((a, i) => <li key={i}><span className="mono">{a.action}</span> {a.entity_type} {a.entity_id} <span className="muted">{formatDateTime(a.created_at)}</span></li>)}</ul>}
      </Card>

      {pending === 'edit' && (
        <FormDialog open title="Sửa người dùng" initial={{ full_name: user.full_name ?? '', phone: user.phone ?? '', role: user.role }} onClose={close} onSubmit={edit}
          fields={[{ name: 'full_name', label: 'Họ tên' }, { name: 'phone', label: 'Số điện thoại' },
            { name: 'role', label: 'Vai trò', type: 'select', required: true, options: ['farmer', 'admin'].map((v) => ({ value: v, label: v })) }]} />
      )}
      {(pending === 'lock' || pending === 'unlock' || pending === 'revoke-sessions') && (
        <ConfirmDialog open danger={pending === 'lock'} onClose={close} onConfirm={simple(pending)}
          title={pending === 'lock' ? 'Khóa tài khoản' : pending === 'unlock' ? 'Mở khóa tài khoản' : 'Buộc đăng xuất'}
          message={pending === 'lock' ? 'Người dùng sẽ bị đăng xuất và không đăng nhập được cho đến khi mở khóa.' : pending === 'unlock' ? 'Cho phép người dùng đăng nhập lại.' : 'Mọi phiên đăng nhập hiện tại của người dùng sẽ bị hủy.'} />
      )}
      {pending === 'deactivate' && (
        <ConfirmDialog open danger confirmLabel="Vô hiệu hóa" title="Vô hiệu hóa tài khoản" onClose={close}
          message="Tài khoản chuyển sang trạng thái vô hiệu hóa, dữ liệu vẫn được giữ để truy vết."
          onConfirm={async () => { await deactivate(); navigate('/users'); }} />
      )}
      {pending === 'reset-password' && (
        <ConfirmDialog open title="Tạo mã đặt lại mật khẩu" confirmLabel="Tạo mã" onClose={close}
          message="Mã chỉ hiển thị một lần, có hiệu lực 1 giờ. Chuyển cho người dùng qua kênh an toàn. (Hệ thống chưa gửi email.)"
          onConfirm={async () => { const r = await act('reset-password'); setToken(r.reset_token ?? null); }} />
      )}
      {token && (
        <Modal open title="Mã đặt lại mật khẩu" onClose={() => setToken(null)}>
          <p className="muted">Sao chép ngay, đóng hộp thoại này sẽ không xem lại được.</p>
          <input className="input mono" readOnly value={token} onFocus={(e) => e.currentTarget.select()} aria-label="Mã đặt lại mật khẩu" />
          <div className="dialog-actions"><button className="btn" onClick={() => setToken(null)}>Đã sao chép</button></div>
        </Modal>
      )}
    </>
  );
}
