import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { api, type Paged } from '../../core/api/client';

/** Danh sách phân trang phía server: GET path?page=&page_size=&...bộ lọc. Giữ dữ liệu cũ khi chuyển trang. */
export function usePagedQuery<T>(key: string, path: string, filters: Record<string, string>, page: number, pageSize = 20) {
  return useQuery({
    queryKey: [key, 'list', filters, page, pageSize],
    queryFn: ({ signal }) => api<Paged<T>>(path, { params: { ...filters, page, page_size: pageSize }, signal }),
    placeholderData: keepPreviousData,
  });
}
