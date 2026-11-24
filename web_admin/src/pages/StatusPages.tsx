import { Link } from 'react-router-dom';

export function ForbiddenPage() {
  return <div className="center-screen"><div className="stack" style={{ textAlign: 'center' }}><h1>403 — Không có quyền</h1><p className="muted">Tài khoản của bạn không được phép xem trang này.</p><Link to="/dashboard">Về tổng quan</Link></div></div>;
}

export function NotFoundPage() {
  return <div className="center-screen"><div className="stack" style={{ textAlign: 'center' }}><h1>404 — Không tìm thấy trang</h1><Link to="/dashboard">Về tổng quan</Link></div></div>;
}
