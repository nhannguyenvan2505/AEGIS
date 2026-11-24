import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../../../core/api/client';
import { formatNumber } from '../../../core/utils/format';
import { Donut, SimpleBar, StatCard, TrendChart } from '../../../shared/charts/Charts';
import { ErrorState, LoadingState } from '../../../shared/feedback/Feedback';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { DISEASE_LABEL } from '../../../shared/status/Badges';
import { Card } from '../../../shared/ui/Card';
import type { Overview } from '../types';

type Rows = { items: Record<string, string | number>[] };

function useStat(path: string, days: number) {
  return useQuery({ queryKey: ['stats', path, days], queryFn: ({ signal }) => api<Rows>(`/stats/${path}`, { params: { days }, signal }) });
}

export default function DashboardPage() {
  const [days, setDays] = useState(30);
  const overview = useQuery({ queryKey: ['stats', 'overview'], queryFn: ({ signal }) => api<Overview>('/stats/overview', { signal }) });
  const detections = useStat('detections', days);
  const diseases = useStat('diseases', days);
  const users = useStat('users', days);
  const risk = useStat('risk', days);
  const o = overview.data;

  return (
    <>
      <PageHeader title="Tổng quan hệ thống" subtitle="Số liệu tính từ cơ sở dữ liệu AEGIS"
        actions={<label className="field">Khoảng thời gian
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>7 ngày</option><option value={30}>30 ngày</option><option value={90}>90 ngày</option>
          </select></label>} />
      {overview.isError && <ErrorState error={overview.error} onRetry={() => void overview.refetch()} />}
      {overview.isLoading && <LoadingState rows={2} />}
      {o && (
        <div className="grid-kpi">
          <StatCard icon="users" label="Người dùng" value={formatNumber(o.users.total)} hint={`${o.users.active_7d} hoạt động 7 ngày`} />
          <StatCard icon="sprout" tone="amber" label="Nông trại" value={formatNumber(o.farms)} hint={`${formatNumber(o.plots)} ruộng`} />
          <StatCard icon="cpu" tone="blue" label="Thiết bị" value={formatNumber(o.devices.total)} hint={`${o.devices.online} online · ${o.devices.offline} offline`} />
          <StatCard icon="scan" tone="violet" label="Chẩn đoán hôm nay" value={formatNumber(o.detections_today)} />
          <StatCard icon="bell" tone="red" label="Cảnh báo đang mở" value={formatNumber(o.alerts_open)} />
        </div>
      )}
      <div className="grid-2">
        <Card title="Chẩn đoán theo ngày">
          {detections.isError ? <ErrorState error={detections.error} /> : <TrendChart data={detections.data?.items ?? []} x="day" y="count" label="Số lượt chẩn đoán theo ngày" />}
        </Card>
        <Card title="Phân bố bệnh">
          {diseases.isError ? <ErrorState error={diseases.error} /> : <Donut data={(diseases.data?.items ?? []).map((r) => ({ ...r, disease: DISEASE_LABEL[String(r.disease)] ?? r.disease }))} name="disease" value="count" label="Phân bố bệnh" />}
        </Card>
        <Card title="Người dùng mới theo tuần">
          {users.isError ? <ErrorState error={users.error} /> : <SimpleBar data={users.data?.items ?? []} x="week" y="count" label="Người dùng mới theo tuần" />}
        </Card>
        <Card title="Phân bố mức rủi ro (dự báo)">
          {risk.isError ? <ErrorState error={risk.error} /> : <SimpleBar data={risk.data?.items ?? []} x="risk_level" y="count" label="Phân bố mức rủi ro" />}
        </Card>
      </div>
    </>
  );
}
