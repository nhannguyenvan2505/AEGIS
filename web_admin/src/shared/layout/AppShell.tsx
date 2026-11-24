import { NavLink, Outlet } from 'react-router-dom';
import { NAV } from '../../app/nav.config';
import { useAuth } from '../../core/auth/AuthContext';
import { Icon } from '../ui/Icon';

const initials = (name: string) => name.trim().split(/\s+/).slice(-2).map((p) => p[0]?.toUpperCase() ?? '').join('') || 'A';

export function AppShell() {
  const { user, logout } = useAuth();
  if (!user) return null;
  const display = user.full_name || user.email;
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">A</span>
          <div><div className="brand-name">AEGIS</div><div className="brand-sub">QUẢN TRỊ HỆ THỐNG</div></div>
        </div>
        <nav aria-label="Điều hướng chính">
          {NAV.map((group) => {
            const items = group.items.filter((i) => i.roles.includes(user.role));
            if (items.length === 0) return null;
            return (
              <div key={group.title}>
                <div className="group">{group.title}</div>
                {items.map((i) => (
                  <NavLink key={i.to} to={i.to} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
                    <Icon name={i.icon} />{i.label}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
        <div className="side-foot">AI nhận diện bệnh lúa và giám sát IoT</div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="spacer" />
          <div className="who"><strong>{display}</strong><div className="small muted">{user.full_name ? `${user.email} · ${user.role}` : user.role}</div></div>
          <div className="avatar" aria-hidden="true">{initials(display)}</div>
          <button className="btn secondary small" onClick={() => void logout()}><Icon name="logout" />Đăng xuất</button>
        </header>
        <main className="content"><Outlet /></main>
      </div>
    </div>
  );
}
