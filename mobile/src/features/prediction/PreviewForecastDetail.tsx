import { router } from 'expo-router';
import { Text, View } from 'react-native';
import { Icon } from '../../components/Design';
import { s } from '../../styles/generated/styles';
import type { Farm, FarmPlot, FarmSeason } from '../farms/client';
import { currentSeason } from './forecastFields';
import { detailDate } from './forecastDetail';
import { usePlotIot } from './IotPreviewContext';
import {
  DetailCard, DetailHero, DetailMeta, DetailReadings, DetailReadingsHeader,
  DetailSuggestion, ForecastDetailPage, detailColors,
} from './components/ForecastDetailUI';

// Local presentation scenario, deliberately separate from saved API forecasts/alerts.
export function PreviewForecastDetail({ farm, plot, seasons }: { farm: Farm; plot: FarmPlot; seasons: FarmSeason[] }) {
  const { readings, forecast, refresh } = usePlotIot(plot.id);
  if (!forecast) return null;
  const { status } = forecast;
  const high = status.tone === 'high';
  return <ForecastDetailPage onRefresh={refresh}>
    <DetailHero status={status} farm={farm} plot={plot} season={currentSeason(seasons)} readState="Đang theo dõi" title={forecast.title}
      time={detailDate(forecast.issuedAt, false, true)} note="Đánh giá điều kiện môi trường để ưu tiên kiểm tra, chưa xác nhận lúa đã nhiễm bệnh." />


    <DetailCard title="Vì sao có dự báo này?">
      <Text testID="forecast-explanation" style={s.forecastDetailBody}>{forecast.explanation}</Text>
      <View style={s.forecastDetailMetadata}><DetailMeta label="Nguồn dữ liệu" value="Số đo IoT của ruộng" />
        <DetailMeta label="Đo lúc" value={detailDate(readings.observedAt, false, true)} /></View>
    </DetailCard>

    <DetailReadingsHeader onRefresh={refresh} />
    <DetailReadings readings={readings} />
    <Text style={s.forecastDetailFootnote}>Đo lúc {detailDate(readings.observedAt, false, true)} · mưa tích lũy 24 giờ.</Text>

    <View testID="forecast-outlook" style={[s.forecastDetailOutlook, high ? s.forecastDetailOutlookHigh : s.forecastDetailOutlookLow]}>
      <View style={s.forecastDetailOutlookLabel}><Icon name={high ? 'alert-triangle' : 'activity'} size={16} color={detailColors[status.tone]} />
        <Text style={[s.forecastDetailOutlookEyebrow, { color: detailColors[status.tone] }]}>{status.label.toLocaleUpperCase('vi-VN')} · {forecast.horizonHours} GIỜ TỚI</Text></View>
      <Text style={s.forecastDetailOutlookTitle}>Đạo ôn lá</Text>
      <Text style={s.forecastDetailBody}>{forecast.outlook}</Text>
      <Text style={s.forecastDetailFootnote}>Dự báo đến {detailDate(forecast.targetWindowEnd, false, true)}.</Text>
    </View>

    <Text accessibilityRole="header" style={s.forecastDetailSectionTitle}>Việc bạn nên làm</Text>
    <DetailSuggestion title={high ? 'Kiểm tra lá trong 24 giờ' : 'Tiếp tục quan sát lá lúa'} icon="aperture"
      body={high ? 'Chú ý vết hình thoi, tâm xám và viền nâu. Chụp rõ hai mặt lá nếu phát hiện dấu hiệu bất thường.' : 'Quan sát lá định kỳ và chụp lại các vùng có dấu hiệu bất thường để kiểm tra thêm.'}
      onPress={() => router.push('/diagnosis')} />
    <DetailSuggestion title={high ? 'Theo dõi độ ẩm sau mưa' : 'Theo dõi điều kiện ruộng'} icon="sliders"
      body={high ? 'Kiểm tra lại số đo sau mưa hoặc khi lá còn ướt; theo dõi pH đất riêng để đánh giá điều kiện đất.' : 'Cập nhật số đo khi có mưa, độ ẩm tăng hoặc điều kiện ruộng thay đổi.'} />
    <DetailSuggestion title="Không phun thuốc chỉ dựa vào dự báo" icon="shield"
      body="Nếu thấy triệu chứng, nhờ cán bộ kỹ thuật xác minh trước khi xử lý." />
  </ForecastDetailPage>;
}
