import { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { ApiError, login, logout, me, register } from '../services/api';
import { tokenStorage } from '../services/tokenStorage';
import type { Session } from '../types/domain';

type AuthState = {
  session: Session | null; ready: boolean; error: string;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  expireSession: (token: string) => Promise<void>;
};
const Context = createContext<AuthState | null>(null);
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const currentSession = useRef<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  const expireSession = useCallback(async (token: string) => {
    if (currentSession.current?.access_token !== token) return;
    currentSession.current = null;
    setSession(null); setError('Phiên đã hết hiệu lực. Vui lòng đăng nhập lại.');
    await tokenStorage.clear();
  }, []);
  useEffect(() => { let active = true;
    void (async () => {
      try { const token = await tokenStorage.get(); if (token) { const result = await me(token); if (active) { currentSession.current = { access_token: token, user: result.user }; setSession(currentSession.current); } } }
      catch (err) { if (err instanceof ApiError && err.status === 401) await tokenStorage.clear(); if (active) setError(err instanceof Error ? err.message : 'Không thể khôi phục phiên.'); }
      finally { if (active) setReady(true); }
    })();
    return () => { active = false; };
  }, []);
  async function signIn(email: string, password: string) {
    if (!ready) throw new Error('Đang khôi phục phiên. Vui lòng đợi.');
    const result = await login(email, password);
    try { await tokenStorage.set(result.access_token); }
    catch (err) { await logout(result.access_token).catch(() => {}); throw err; }
    currentSession.current = result;
    setError(''); setSession(result);
  }
  async function signUp(email: string, password: string) { await register(email, password); }
  async function signOut() {
    const departing = currentSession.current;
    if (departing) { try { await logout(departing.access_token); } catch (err) { if (!(err instanceof ApiError && err.status === 401)) throw err; } }
    if (currentSession.current !== departing) return;
    await tokenStorage.clear(); currentSession.current = null; setSession(null); setError('');
  }
  return <Context.Provider value={{ session, ready, error, signIn, signUp, signOut, expireSession }}>{children}</Context.Provider>;
}
export function useAuth() { const value = useContext(Context); if (!value) throw new Error('Missing AuthProvider'); return value; }
