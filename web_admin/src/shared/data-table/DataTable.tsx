import type { ReactNode } from 'react';
import { EmptyState, ErrorState, LoadingState } from '../feedback/Feedback';

export interface Column<T> { header: string; cell(row: T): ReactNode; width?: number | string }

interface Props<T> {
  columns: Column<T>[];
  rows: T[] | undefined;
  rowKey(row: T): string | number;
  loading?: boolean;
  error?: unknown;
  onRetry?(): void;
  onRowClick?(row: T): void;
  empty?: string;
}

/** Bảng dùng chung. Có đủ 4 trạng thái: đang tải, lỗi, rỗng, có dữ liệu. */
export function DataTable<T>({ columns, rows, rowKey, loading, error, onRetry, onRowClick, empty }: Props<T>) {
  if (error) return <ErrorState error={error} onRetry={onRetry} />;
  if (loading && !rows) return <LoadingState />;
  if (!rows || rows.length === 0) return <EmptyState>{empty}</EmptyState>;
  return (
    <div className="table-wrap">
      <table className="table">
        <thead><tr>{columns.map((c) => <th key={c.header} style={{ width: c.width }}>{c.header}</th>)}</tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className={onRowClick ? 'clickable' : undefined} onClick={onRowClick ? () => onRowClick(row) : undefined}>
              {columns.map((c) => <td key={c.header}>{c.cell(row)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage(p: number): void }) {
  const pages = Math.max(Math.ceil(total / pageSize), 1);
  return (
    <div className="pagination">
      <span className="muted small">{total} bản ghi · trang {page}/{pages}</span>
      <button className="btn secondary small" disabled={page <= 1} onClick={() => onPage(page - 1)}>Trước</button>
      <button className="btn secondary small" disabled={page >= pages} onClick={() => onPage(page + 1)}>Sau</button>
    </div>
  );
}

export interface FilterDef { name: string; label: string; type?: 'text' | 'select'; options?: { value: string; label: string }[]; placeholder?: string }

export function FilterBar({ defs, values, onChange }: { defs: FilterDef[]; values: Record<string, string>; onChange(name: string, value: string): void }) {
  return (
    <div className="filters">
      {defs.map((d) => (
        <label key={d.name} className="field">{d.label}
          {d.type === 'select' ? (
            <select value={values[d.name] ?? ''} onChange={(e) => onChange(d.name, e.target.value)}>
              <option value="">Tất cả</option>
              {d.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          ) : (
            <input value={values[d.name] ?? ''} placeholder={d.placeholder} onChange={(e) => onChange(d.name, e.target.value)} />
          )}
        </label>
      ))}
    </div>
  );
}
