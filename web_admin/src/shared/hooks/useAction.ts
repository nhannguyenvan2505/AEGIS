import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../../core/api/errors';
import { useToast } from '../feedback/Toast';

/**
 * Thao tác ghi: gọi API, báo kết quả bằng toast, rồi làm mới các query theo tiền tố khóa (ví dụ 'users').
 * Lỗi được ném lại để hộp thoại gọi nó hiển thị tại chỗ.
 */
export function useAction<V = void, R = unknown>(fn: (v: V) => Promise<R>, opts: { invalidate: string[]; success?: string }) {
  const qc = useQueryClient();
  const { notify } = useToast();
  const mutation = useMutation({
    mutationFn: fn,
    onSuccess: () => {
      for (const key of opts.invalidate) qc.invalidateQueries({ queryKey: [key] });
      if (opts.success) notify(opts.success);
    },
    onError: (e) => { if (!(e instanceof ApiError)) notify('Đã xảy ra lỗi.', 'error'); },
  });
  return mutation.mutateAsync;
}
