import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

export type Filters = Record<string, string>;

/**
 * Bộ lọc và số trang lưu trên URL (?status=open&page=2) để tải lại trang/chia sẻ liên kết vẫn giữ nguyên.
 * Đổi bộ lọc luôn đưa về trang 1.
 */
export function useUrlFilters(keys: readonly string[]) {
  const [params, setParams] = useSearchParams();
  const filters = useMemo(() => {
    const out: Filters = {};
    for (const key of keys) out[key] = params.get(key) ?? '';
    return out;
  }, [params, keys]);
  const page = Math.max(Number(params.get('page')) || 1, 1);

  const setFilter = useCallback((key: string, value: string) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) next.set(key, value); else next.delete(key);
      next.delete('page');
      return next;
    }, { replace: true });
  }, [setParams]);

  const setPage = useCallback((value: number) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value > 1) next.set('page', String(value)); else next.delete('page');
      return next;
    }, { replace: true });
  }, [setParams]);

  return { filters, page, setFilter, setPage };
}
