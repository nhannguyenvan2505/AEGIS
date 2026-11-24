import type { ReactNode } from 'react';

export function Card({ title, actions, children }: { title?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      {(title || actions) && <div className="card-head">{title && <h2>{title}</h2>}<div className="spacer" />{actions}</div>}
      {children}
    </section>
  );
}

/** Danh sách "nhãn: giá trị". */
export function KeyValue({ rows }: { rows: [string, ReactNode][] }) {
  return <dl className="kv">{rows.map(([k, v]) => <div key={k} style={{ display: 'contents' }}><dt>{k}</dt><dd>{v ?? '—'}</dd></div>)}</dl>;
}

export function JsonView({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="muted">—</span>;
  const data = typeof value === 'string' ? (() => { try { return JSON.parse(value); } catch { return value; } })() : value;
  return <pre className="json">{JSON.stringify(data, null, 2)}</pre>;
}
