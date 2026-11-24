import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { router } from 'expo-router';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';
import { Icon } from '../../components/Design';
import { s } from '../../styles/generated/styles';
import { useAuth } from '../../state/AuthContext';
import { useFarmWorkspace } from '../farms/FarmWorkspace';
import type { FarmPlot } from '../farms/client';
import { useFarmActionFocus, useFarmData } from '../farms/useFarmData';
import { HomePlotPicker } from '../dashboard/components/HomePlotPicker';
import { usePlotIot } from '../prediction/IotPreviewContext';
import { ProfileButton, ProfileNotice, ProfilePage, ProfileSheet } from '../profile/components/ProfileUI';
import { reportDataSource } from './reportData';
import { createReportFile, shareReportFile, type ReportFormat } from './reportExport';
import { defaultReportRange, reportConclusion, reportDate, reportDay, reportKey, reportMetrics, reportNumber, reportRangeLabel, reportTimestamp, reportTotals, type ReportData, type ReportInput } from './reportModel';
import { EnvironmentChart, RiskChart } from './components/ReportCharts';
import { ReportFullPreview, ReportPaper } from './components/ReportDocumentPreview';
import { ReportPeriodPicker } from './components/ReportPeriodPicker';

function ReportCard({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return <View style={s.reportCard}><View style={s.reportCardHeading}><Text accessibilityRole="header" style={s.reportCardTitle}>{title}</Text>{action}</View>{children}</View>;
}

function ReportSession() {
  const { session } = useAuth();
  const workspace = useFarmWorkspace();
  const { loadPlots, selectedFarmId, selectFarm } = workspace;
  const farm = workspace.farms.find(item => item.id === selectedFarmId) ?? workspace.farms[0];
  const farmId = farm?.id;
  const [selectedPlot, setSelectedPlot] = useState<FarmPlot>();
  const [range, setRange] = useState(defaultReportRange);
  const [sheet, setSheet] = useState<'plot' | 'period' | 'alerts'>();
  const [preview, setPreview] = useState<ReportData>();
  const [exporting, setExporting] = useState<ReportFormat>();
  const [exportError, setExportError] = useState('');
  const exportingRef = useRef(false);
  const active = useRef(true);
  const stillHere = useFarmActionFocus();
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const plotsLoader = useCallback(async () => ({ farmId, plots: farmId ? await loadPlots(farmId) : [] }), [farmId, loadPlots]);
  const plotsResource = useFarmData(plotsLoader);
  const plots = plotsResource.data?.farmId === farmId ? plotsResource.data?.plots ?? [] : [];
  const plot = plotsResource.data?.farmId === farmId ? plots.find(item => item.id === selectedPlot?.id) ?? plots[0]
    : selectedPlot?.farm_id === farmId ? selectedPlot : undefined;
  const { readings } = usePlotIot(plot?.id);
  const input: ReportInput | null = farm && plot ? { farm, plot, range, latest: readings } : null;
  const request = input ? JSON.stringify(input) : '';
  const requestedKey = input ? reportKey(input) : '';
  const token = session?.access_token;
  const loader = useCallback(() => request ? reportDataSource.load(JSON.parse(request) as ReportInput, token) : Promise.resolve(null), [request, token]);
  const resource = useFarmData(loader);
  const report = resource.data?.key === requestedKey ? resource.data : null;
  const problem = workspace.error || plotsResource.error || resource.error;
  const loading = !problem && (workspace.loading || plotsResource.loading || resource.loading || (!!request && !report));
  const totals = report ? reportTotals(report) : null;
  const hasData = !!report?.points.length;
  function retry() { setExportError(''); void workspace.load(); plotsResource.reload(); resource.reload(); }
  function openCurrentForecast() {
    setSheet(undefined);
    if (session && farm && plot) router.push({ pathname: '/analysis/[plotId]', params: { farmId: farm.id, plotId: plot.id } });
    else router.push('/analysis');
  }
  async function exportFile(format: ReportFormat) {
    if (!report || !hasData || loading || exportingRef.current) return;
    exportingRef.current = true; setExporting(format); setExportError('');
    try {
      const uri = await createReportFile(report, format);
      if (stillHere()) await shareReportFile(uri, format);
    } catch {
      if (stillHere()) setExportError('Chưa xuất được báo cáo PDF. Vui lòng thử lại.');
    } finally { exportingRef.current = false; if (active.current) setExporting(undefined); }
  }

  return <ProfilePage title="Báo cáo thống kê" backTo="/profile">
    <Pressable testID="report-select-plot" accessibilityRole="button" accessibilityLabel="Chọn ruộng báo cáo" disabled={!!exporting}
      onPress={() => setSheet('plot')} style={({ pressed }) => [s.reportPlotSelect, pressed && s.profilePressed]}>
      <Icon name="feather" color="#0b7a54" size={24} /><View style={s.profileGrow}><Text style={s.reportPlotName}>{plot?.name ?? (workspace.loading || plotsResource.loading ? 'Đang tải ruộng…' : 'Chọn ruộng')}</Text>
        <Text style={s.reportMuted}>{plot ? [plot.area_ha === null ? 'Chưa nhập diện tích' : `${reportNumber(plot.area_ha)} ha`, plot.location_text || farm?.name].filter(Boolean).join(' · ') : 'Chọn nông trại và ruộng cần tổng hợp'}</Text></View>
      <Icon name="chevron-down" color="#566a63" size={20} />
    </Pressable>
    <View><Text style={s.reportPeriodLabel}>Kỳ báo cáo</Text>
      <Pressable testID="report-select-period" accessibilityRole="button" accessibilityLabel="Chọn kỳ báo cáo" disabled={!!exporting}
        onPress={() => setSheet('period')} style={({ pressed }) => [s.reportPeriodSelect, pressed && s.profilePressed]}>
        <Icon name="calendar" color="#566a63" size={19} /><Text style={s.reportPeriodValue}>{reportRangeLabel(range)}</Text><Icon name="chevron-down" color="#566a63" size={19} />
      </Pressable>
    </View>
    {report?.asOf && !loading && <View style={s.reportAsOf}><Icon name="check-circle" size={16} color="#0b7a54" /><Text style={s.reportMuted}>Đến {reportTimestamp(report.asOf)}{report.source === 'preview' ? ' · Dữ liệu minh họa' : ''}</Text></View>}
    {!!problem && <><ProfileNotice message={problem} /><ProfileButton title="Thử tải lại báo cáo" outline onPress={retry} /></>}

    {loading && <View testID="report-loading" style={s.reportLoading}>
      <ActivityIndicator color="#0b7a54" /><View style={s.profileGrow}><Text style={s.reportPlotName}>Đang tổng hợp báo cáo</Text><Text style={s.reportMuted}>{plot?.name ?? 'Ruộng của bạn'} · {reportRangeLabel(range)}</Text></View>
    </View>}
    {!loading && !problem && !hasData && <View testID="report-empty" style={s.reportEmpty}>
      <Icon name="bar-chart-2" size={38} color="#0b7a54" /><Text style={s.reportEmptyTitle}>Chưa có dữ liệu báo cáo</Text>
      <Text style={s.reportEmptyText}>{plot?.name ?? 'Ruộng của bạn'} · {reportRangeLabel(range)}. Hãy thử chọn ruộng khác hoặc mở rộng khoảng ngày.</Text>
      <ProfileButton title="Đổi ruộng hoặc kỳ báo cáo" outline onPress={() => setSheet(plot ? 'period' : 'plot')} />
    </View>}

    {!loading && !problem && hasData && report && totals && <>
      <ReportCard title="Quan trắc môi trường">
        <Text style={s.reportMuted}>{reportRangeLabel(range)} · Mỗi ngày một số đo đại diện. Các đường nối số đo để dễ theo dõi.</Text>
        {reportMetrics.map(metric => <EnvironmentChart key={metric.key} metric={metric} points={report.points} />)}
        <Text style={s.reportFootnote}>Lượng mưa tích lũy 24 giờ. Biểu đồ hiển thị tối đa 7 mốc đại diện trong kỳ.</Text>
      </ReportCard>
      <ReportCard title="Khám lúa bằng AI" action={<Pressable accessibilityRole="button" accessibilityLabel="Mở khám lúa bằng ảnh" onPress={() => router.push('/diagnosis')} style={s.reportIconAction}><Icon name="maximize" size={19} color="#0b7a54" /></Pressable>}>
        <Text style={s.reportMuted}>{totals.scans} lần đánh giá ảnh trong kỳ</Text>
        <View style={s.reportAiStats}><View style={s.reportAiStat}><Text style={s.reportAiCount}>{totals.suspected}</Text><Text style={s.reportMuted}>Nghi ngờ đạo ôn lá</Text></View>
          <View style={s.reportAiStat}><Text style={s.reportAiCount}>{totals.unclear}</Text><Text style={s.reportMuted}>Chưa thấy dấu hiệu rõ</Text></View></View>
        <View style={s.reportSummaryRow}><Text style={s.reportMuted}>Bệnh được xác nhận</Text><Text style={s.reportSummaryValue}>Chưa có xác minh</Text></View>
        <Text style={s.reportFootnote}>Số lần AI nghi ngờ không phải số ca nhiễm bệnh. {report.scans.map(scan => `${scan.result === 'suspected' ? 'Nghi ngờ' : 'Chưa thấy rõ'}: ${reportTimestamp(scan.at)}`).join(' · ')}</Text>
      </ReportCard>
      <ReportCard title="Xu hướng dự báo nguy cơ">
        <Text style={s.reportMuted}>Số dự báo theo ngày · {reportRangeLabel(range)}</Text><RiskChart risks={report.risks} />
        <Text style={s.reportFootnote}>{totals.high} dự báo nguy cơ cao · {totals.low} dự báo nguy cơ thấp. Đây là dự báo từ điều kiện môi trường, không phải tỷ lệ nhiễm bệnh.</Text>
      </ReportCard>
      <ReportCard title="Tổng hợp cảnh báo">
        <View style={s.reportSummaryRow}><Text style={s.reportMuted}>Ưu tiên tại {plot?.name}</Text><Text style={s.reportSummaryValue}>{totals.alerts} cảnh báo</Text></View>
        <View style={s.reportSummaryRow}><Text style={s.reportMuted}>Chưa đọc</Text><Text style={s.reportSummaryValue}>{totals.unread} thông báo</Text></View>
        {report.alerts.length ? <Pressable testID="report-open-alerts" accessibilityRole="button" onPress={() => setSheet('alerts')} style={s.reportAlertLink}>
          <Text style={s.reportAlertLinkText}>{report.alerts.at(-1)!.title} · {reportDate(reportDay(Date.parse(report.alerts.at(-1)!.at)), true)}</Text><Icon name="chevron-right" size={20} color="#0b7a54" />
        </Pressable> : <Text style={s.reportFootnote}>Không có cảnh báo trong kỳ đã chọn.</Text>}
      </ReportCard>
      <ReportCard title="Xem trước báo cáo" action={<Icon name="file-text" size={20} color="#0b7a54" />}>
        <ReportPaper report={report} compact />
        <Pressable testID="report-open-preview" accessibilityRole="button" onPress={() => setPreview(report)} style={s.reportPreviewLink}>
          <Text style={s.reportAlertLinkText}>Xem toàn bộ 2 trang</Text><Icon name="maximize-2" size={19} color="#0b7a54" />
        </Pressable>
      </ReportCard>
    </>}

    {(loading || (hasData && !problem)) && <ProfileButton title={exporting === 'pdf' ? 'Đang tạo PDF…' : 'Xuất PDF'} icon="file-text" testID="report-export-pdf"
      busy={exporting === 'pdf'} disabled={loading || !hasData || !!exporting} onPress={() => void exportFile('pdf')} />}
    {!!exportError && <ProfileNotice message={exportError} />}
    {hasData && !loading && <Text style={s.reportFootnote}>Xuất theo ruộng và kỳ đang chọn. Kết quả AI chỉ hỗ trợ theo dõi, không thay thế xác minh thực tế.</Text>}

    {sheet === 'plot' && <ProfileSheet title="Chọn ruộng báo cáo" onClose={() => setSheet(undefined)}>
      <HomePlotPicker farmId={farmId} plotId={plot?.id} onClose={() => setSheet(undefined)} onSelect={item => { selectFarm(item.farm_id); setSelectedPlot(item); setExportError(''); setSheet(undefined); }} />
    </ProfileSheet>}
    {sheet === 'period' && <ProfileSheet title="Chọn kỳ báo cáo" onClose={() => setSheet(undefined)}>
      <ReportPeriodPicker range={range} onApply={value => { setRange(value); setExportError(''); setSheet(undefined); }} />
    </ProfileSheet>}
    {sheet === 'alerts' && report && <ProfileSheet title="Cảnh báo trong kỳ" onClose={() => setSheet(undefined)}>
      {report.alerts.map(alert => <View key={alert.id} style={s.reportAlertDetail}><Text style={s.reportPlotName}>{alert.title}</Text><Text style={s.reportMuted}>{reportTimestamp(alert.at)} · {alert.state === 'unread' ? 'Chưa đọc' : 'Đã đọc'}</Text></View>)}
      <Text style={s.reportMuted}>{reportConclusion(report)}</Text><ProfileButton title="Xem dự báo hiện tại" onPress={openCurrentForecast} />
      <ProfileButton title="Đóng" outline onPress={() => setSheet(undefined)} />
    </ProfileSheet>}
    {preview && <ReportFullPreview report={preview} onClose={() => setPreview(undefined)} />}
  </ProfilePage>;
}

export function ReportsScreen() {
  const { session } = useAuth();
  return <ReportSession key={session?.user.id ?? 'report-demo'} />;
}
