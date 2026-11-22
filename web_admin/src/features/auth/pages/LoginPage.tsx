import { useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { ApiError } from '../../../core/api/errors';
import { canAccess } from '../../../app/nav.config';
import { useAuth } from '../../../core/auth/AuthContext';
import { Icon } from '../../../shared/ui/Icon';

export default function LoginPage() {
  const { user, login } = useAuth();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? '/dashboard';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  // Chỉ quay lại trang cũ nếu vai trò vừa đăng nhập được phép vào.
  if (user) return <Navigate to={canAccess(from, user.role) ? from : '/dashboard'} replace />;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true); setError(null);
    try { await login(email.trim(), password); }
    catch (e) { setError(e as Error); }
    finally { setBusy(false); }
  };

  const wait = error instanceof ApiError && error.status === 429 && error.retryAfter ? ` Thử lại sau ${error.retryAfter} giây.` : '';

  return (
    <div className="login">
      <aside className="login-aside" aria-hidden="true">
        <div className="brand"><span className="brand-mark">A</span><div><strong style={{ fontSize: 20 }}>AEGIS</strong><div className="small" style={{ color: '#8fb3a4' }}>QUẢN TRỊ HỆ THỐNG</div></div></div>
        <div>
          <h2>Giám sát bệnh lúa bằng AI và IoT</h2>
          <p>Theo dõi người dùng, nông trại, thiết bị cảm biến và kết quả chẩn đoán trong một nơi duy nhất.</p>
        </div>
        <ul>
          <li><span className="dot"><Icon name="leaf" /></span>Nông trại, ruộng và mùa vụ của khách hàng</li>
          <li><span className="dot"><Icon name="wifi" /></span>4 loại cảm biến cho mỗi ruộng</li>
          <li><span className="dot"><Icon name="shield" /></span>Phân quyền và nhật ký mọi thao tác</li>
        </ul>
      </aside>
      <div className="login-main">
      <form className="card login-card" onSubmit={submit}>
        <div><h1>AEGIS Admin</h1><div className="muted sub">Đăng nhập bằng tài khoản quản trị.</div></div>
        <label className="field">Email
          <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="field">Mật khẩu
          <input type="password" autoComplete="current-password" required minLength={12} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <div className="error-box" role="alert">{error.message}{wait}</div>}
        <button className="btn" type="submit" disabled={busy} style={{ justifyContent: 'center', padding: '11px 16px' }}>{busy ? 'Đang đăng nhập…' : 'Đăng nhập'}</button>
      </form>
      </div>
    </div>
  );
}
