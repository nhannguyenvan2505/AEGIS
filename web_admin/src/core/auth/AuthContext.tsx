import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, setUnauthorizedHandler } from '../api/client';
import { tokenStorage } from './tokenStorage';

export type Role = 'admin';
export interface AdminUser { id: string; email: string; full_name: string | null; role: Role }

interface AuthState {
  user: AdminUser | null;
  loading: boolean;
  login(email: string, password: string): Promise<void>;
  logout(): Promise<void>;
  can(...roles: Role[]): boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AdminUser | null>(null);
  const [loading, setLoading] = useState(() => tokenStorage.get() !== null);

  const clear = useCallback(() => { tokenStorage.clear(); setUser(null); }, []);

  useEffect(() => {
    setUnauthorizedHandler(clear);
    return () => setUnauthorizedHandler(null);
  }, [clear]);

  useEffect(() => {
    if (!tokenStorage.get()) return;
    let active = true;
    api<{ user: AdminUser }>('/auth/me')
      .then((r) => { if (active) setUser(r.user); })
      .catch(() => { if (active) clear(); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [clear]);

  const login = useCallback(async (email: string, password: string) => {
    const r = await api<{ access_token: string; user: AdminUser }>('/auth/login', {
      method: 'POST', body: { email, password },
    });
    tokenStorage.set(r.access_token);
    setUser(r.user);
  }, []);

  const logout = useCallback(async () => {
    try { await api('/auth/logout', { method: 'POST' }); } catch { /* token có thể đã hết hạn */ }
    clear();
  }, [clear]);

  const value = useMemo<AuthState>(() => ({
    user, loading, login, logout,
    can: (...roles) => user !== null && roles.includes(user.role),
  }), [user, loading, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth phải nằm trong AuthProvider');
  return ctx;
}
