import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { EmptyState } from '../feedback/Feedback';
import { Icon, type IconName } from '../ui/Icon';

const COLORS = ['#0e8a5f', '#d98b1b', '#c0392b', '#1d5fa8', '#6b4fc9', '#8a9b94'];
const GRID = '#edf1ee';
const TOOLTIP = { borderRadius: 10, border: '1px solid #e0e7e3', boxShadow: '0 6px 20px rgba(16,38,31,0.12)', fontSize: 13 };

export function StatCard({ label, value, hint, icon, tone }: { label: string; value: string | number; hint?: string; icon?: IconName; tone?: 'amber' | 'blue' | 'red' | 'violet' }) {
  return (
    <div className="card kpi">
      {icon && <div className={`kpi-icon${tone ? ` ${tone}` : ''}`}><Icon name={icon} /></div>}
      <div><div className="label">{label}</div><div className="value">{value}</div>{hint && <div className="hint">{hint}</div>}</div>
    </div>
  );
}

type Point = Record<string, string | number>;

export function TrendChart({ data, x, y, label }: { data: Point[]; x: string; y: string; label: string }) {
  if (data.length === 0) return <EmptyState>Chưa có dữ liệu trong khoảng này.</EmptyState>;
  return (
    <div role="img" aria-label={label} style={{ height: 240 }}>
      <ResponsiveContainer>
        <LineChart data={data}><CartesianGrid stroke={GRID} vertical={false} /><XAxis dataKey={x} fontSize={12} tickLine={false} axisLine={false} /><YAxis allowDecimals={false} fontSize={12} tickLine={false} axisLine={false} /><Tooltip contentStyle={TOOLTIP} />
          <Line type="monotone" dataKey={y} stroke="#0e8a5f" strokeWidth={2.5} dot={false} /></LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function SimpleBar({ data, x, y, label }: { data: Point[]; x: string; y: string; label: string }) {
  if (data.length === 0) return <EmptyState>Chưa có dữ liệu trong khoảng này.</EmptyState>;
  return (
    <div role="img" aria-label={label} style={{ height: 240 }}>
      <ResponsiveContainer>
        <BarChart data={data}><CartesianGrid stroke={GRID} vertical={false} /><XAxis dataKey={x} fontSize={12} tickLine={false} axisLine={false} /><YAxis allowDecimals={false} fontSize={12} tickLine={false} axisLine={false} /><Tooltip contentStyle={TOOLTIP} />
          <Bar dataKey={y} fill="#1fb583" radius={[6, 6, 0, 0]} /></BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Donut({ data, name, value, label }: { data: Point[]; name: string; value: string; label: string }) {
  if (data.length === 0) return <EmptyState>Chưa có dữ liệu trong khoảng này.</EmptyState>;
  return (
    <div role="img" aria-label={label} style={{ height: 240 }}>
      <ResponsiveContainer>
        <PieChart margin={{ top: 20, right: 20, bottom: 0, left: 20 }}><Pie data={data} dataKey={value} nameKey={name} innerRadius={55} outerRadius={85} paddingAngle={2} label>
          {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Pie><Tooltip contentStyle={TOOLTIP} /><Legend /></PieChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Nhiều đường (nhiệt độ, độ ẩm...). */
export function MultiLine({ data, x, lines, label }: { data: Point[]; x: string; lines: { key: string; name: string; color: string }[]; label: string }) {
  if (data.length === 0) return <EmptyState>Chưa có dữ liệu.</EmptyState>;
  return (
    <div role="img" aria-label={label} style={{ height: 260 }}>
      <ResponsiveContainer>
        <LineChart data={data}><CartesianGrid stroke={GRID} vertical={false} /><XAxis dataKey={x} fontSize={11} /><YAxis fontSize={12} /><Tooltip contentStyle={TOOLTIP} />
          {lines.map((l) => <Line key={l.key} name={l.name} type="monotone" dataKey={l.key} stroke={l.color} strokeWidth={2} dot={false} />)}</LineChart>
      </ResponsiveContainer>
    </div>
  );
}
