import { ApiError } from '../../core/api/errors';

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error instanceof ApiError ? error : null;
  const hint =
    e?.code === 'admin_unavailable' ? ' Backend cần chạy với MySQL (STORAGE_BACKEND=mysql).'
    : e?.status === 429 && e.retryAfter ? ` Thử lại sau ${e.retryAfter} giây.` : '';
  return (
    <div className="error-box" role="alert">
      <strong>{e ? e.message : 'Đã xảy ra lỗi.'}</strong>{hint}
      {e?.requestId && <div className="rid">Mã yêu cầu: {e.requestId}</div>}
      {onRetry && <div style={{ marginTop: 8 }}><button className="btn secondary small" onClick={onRetry}>Thử lại</button></div>}
    </div>
  );
}

export function LoadingState({ rows = 4 }: { rows?: number }) {
  return <div aria-busy="true" aria-label="Đang tải">{Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton" />)}</div>;
}

export function EmptyState({ children = 'Không có dữ liệu.' }: { children?: string }) {
  return <div className="empty">{children}</div>;
}

/** Bắt buộc hiển thị ở mọi nơi có dữ liệu thiết bị/telemetry/dự báo mô phỏng. */
export function SimulatedDataBanner({ children }: { children?: string }) {
  return (
    <div className="notice" role="note">
      <strong>Dữ liệu mô phỏng.</strong> {children ?? 'Telemetry IoT hiện là mock/synthetic, chưa phải dữ liệu thực địa.'}
    </div>
  );
}
