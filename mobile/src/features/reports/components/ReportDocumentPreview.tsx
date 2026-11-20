import { Modal, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Icon } from '../../../components/Design';
import { s } from '../../../styles/generated/styles';
import { reportConclusion, reportDate, reportMetrics, reportNumber, reportRangeLabel, reportTimestamp, reportTotals, sampleReportPoints, type ReportData } from '../reportModel';

export function ReportPaper({ report, page = 1, compact = false }: { report: ReportData; page?: 1 | 2; compact?: boolean }) {
  const totals = reportTotals(report);
  return <View style={s.reportPaper}>
    <Text style={s.reportPaperBrand}>AEGIS</Text><Text style={s.reportPaperTitle}>BÁO CÁO THEO DÕI RUỘNG</Text>
    <Text style={s.reportPaperText}>{report.plot.name} · {report.farm.name}</Text><Text style={s.reportPaperText}>{reportRangeLabel(report.range)}</Text>
    <View style={s.reportPaperRule} />
    {page === 1 ? <>
      {[
        ['Đánh giá ảnh AI', `${totals.scans} lần`], ['Gợi ý triệu chứng', `${totals.suspected} lần`], ['Dự báo nguy cơ', `${totals.forecasts} lần`],
      ].map(([label, value]) => <View key={label} style={s.reportPaperRow}><Text style={s.reportPaperMuted}>{label}</Text><Text style={s.reportPaperValue}>{value}</Text></View>)}
      {!compact && <><Text style={s.reportPaperHeading}>Quan trắc môi trường</Text>
        {sampleReportPoints(report.points).map(point => <View key={point.day} style={s.reportPaperObservation}>
          <Text style={s.reportPaperValue}>{reportDate(point.day)}</Text><Text style={s.reportPaperText}>{reportMetrics.map(metric => `${metric.label}: ${reportNumber(point[metric.key])} ${metric.unit}`).join(' · ')}</Text>
        </View>)}
      </>}
    </> : <>
      <Text style={s.reportPaperHeading}>Khám lúa bằng AI</Text>
      {report.scans.map(scan => <Text key={scan.id} style={s.reportPaperText}>{reportTimestamp(scan.at)} · {scan.result === 'suspected' ? 'Nghi ngờ đạo ôn lá' : 'Chưa thấy dấu hiệu rõ'}</Text>)}
      {!report.scans.length && <Text style={s.reportPaperMuted}>Chưa có đánh giá ảnh trong kỳ.</Text>}
      <Text style={s.reportPaperHeading}>Dự báo và cảnh báo</Text>
      <Text style={s.reportPaperText}>{totals.high} dự báo nguy cơ cao · {totals.low} dự báo nguy cơ thấp</Text>
      {report.alerts.map(alert => <Text key={alert.id} style={s.reportPaperText}>{reportTimestamp(alert.at)} · {alert.title}</Text>)}
      <Text style={s.reportPaperMuted}>Bệnh được xác nhận: chưa có xác minh.</Text>
    </>}
    <Text style={s.reportPaperConclusion}>{reportConclusion(report)}</Text>
    <View style={s.reportPaperFooter}><Text style={s.reportPaperSmall}>{report.source === 'preview' ? 'Dữ liệu minh họa' : 'Dữ liệu theo dõi'}</Text><Text style={s.reportPaperSmall}>Trang {page}/2</Text></View>
  </View>;
}

export function ReportFullPreview({ report, onClose }: { report: ReportData; onClose: () => void }) {
  return <Modal visible animationType="slide" onRequestClose={onClose}>
    <SafeAreaView style={s.reportPreviewPage}>
      <View style={s.reportPreviewHeader}><Pressable accessibilityRole="button" accessibilityLabel="Đóng xem trước báo cáo" onPress={onClose} style={s.profileHeaderButton}>
        <Icon name="arrow-left" size={23} color="#7385a4" /></Pressable><Text style={s.profileTitle}>Xem trước báo cáo</Text><Text style={s.reportMuted}>2 trang</Text></View>
      <ScrollView contentContainerStyle={s.reportPreviewScroll}><View style={s.profileColumn}><ReportPaper report={report} /><ReportPaper report={report} page={2} /></View></ScrollView>
    </SafeAreaView>
  </Modal>;
}
