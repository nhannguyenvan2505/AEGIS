import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

export interface Crumb { label: string; to?: string }

export function PageHeader({ title, subtitle, crumbs, actions }: { title: string; subtitle?: string; crumbs?: Crumb[]; actions?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        {crumbs && (
          <nav className="breadcrumbs" aria-label="Đường dẫn">
            {crumbs.map((c, i) => <span key={c.label}>{i > 0 && ' / '}{c.to ? <Link to={c.to}>{c.label}</Link> : c.label}</span>)}
          </nav>
        )}
        <h1>{title}</h1>
        {subtitle && <div className="sub">{subtitle}</div>}
      </div>
      <div className="spacer" />
      {actions && <div className="row">{actions}</div>}
    </div>
  );
}
