import { api } from '../../core/api/client';
import type { UserDetail } from './types';

export const getUser = (id: string, signal?: AbortSignal) => api<UserDetail>(`/users/${id}`, { signal });
export const createUser = (body: Record<string, unknown>) => api<{ id: string }>('/users', { method: 'POST', body });
export const updateUser = (id: string, body: Record<string, unknown>) => api(`/users/${id}`, { method: 'PUT', body });
export const userAction = (id: string, action: 'lock' | 'unlock' | 'revoke-sessions' | 'reset-password') => api<{ reset_token?: string }>(`/users/${id}/${action}`, { method: 'POST' });
export const deactivateUser = (id: string) => api(`/users/${id}`, { method: 'DELETE' });
