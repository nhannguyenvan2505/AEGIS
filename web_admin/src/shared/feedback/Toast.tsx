import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

interface ToastItem { id: number; text: string; tone: 'ok' | 'error' }
const ToastContext = createContext<{ notify(text: string, tone?: 'ok' | 'error'): void } | null>(null);
let counter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const notify = useCallback((text: string, tone: 'ok' | 'error' = 'ok') => {
    const id = ++counter;
    setItems((list) => [...list, { id, text, tone }]);
    setTimeout(() => setItems((list) => list.filter((t) => t.id !== id)), 4500);
  }, []);
  const value = useMemo(() => ({ notify }), [notify]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div aria-live="polite" className="toast-stack">
        {items.map((t) => <div key={t.id} className={t.tone === 'error' ? 'error-box' : 'notice ok'}>{t.text}</div>)}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast phải nằm trong ToastProvider');
  return ctx;
};
