import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { ApiError } from '../core/api/errors';
import { AuthProvider } from '../core/auth/AuthContext';
import { ToastProvider } from '../shared/feedback/Toast';

export const makeQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      // Không thử lại lỗi do client (401/403/404/422...): chỉ thử lại lỗi mạng/máy chủ.
      retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
    },
  },
});

export function Providers({ children, client }: { children: ReactNode; client?: QueryClient }) {
  return (
    <QueryClientProvider client={client ?? makeQueryClient()}>
      <ToastProvider><AuthProvider>{children}</AuthProvider></ToastProvider>
    </QueryClientProvider>
  );
}
