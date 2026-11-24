import type { ReactNode } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth, type Role } from './AuthContext';

/** Chặn truy cập: chưa đăng nhập về /login, sai vai trò về /403. Backend vẫn là nơi chặn thật (403). */
export function RequireRole({ roles, children }: { roles?: Role[]; children?: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="center-screen">Đang kiểm tra phiên…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/403" replace />;
  return <>{children ?? <Outlet />}</>;
}
