import { useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { s } from '../../../styles/generated/styles';
import { reportDate, reportNumber, sampleReportPoints, type ReportMetric, type ReportPoint, type ReportRisk } from '../reportModel';

export function EnvironmentChart({ metric, points }: { metric: ReportMetric; points: ReportPoint[] }) {
  const [width, setWidth] = useState(0);
  const samples = sampleReportPoints(points);
  const values = samples.map(point => point[metric.key]).filter((value): value is number => value !== null && Number.isFinite(value));
  const floor = values.length ? Math.floor(Math.min(...values)) : 0;
  const minimum = metric.key === 'rainfall' ? 0 : floor;
  const maximum = Math.max(minimum + 1, values.length ? Math.ceil(Math.max(...values)) : 1);
  const height = 94;
  const position = (point: ReportPoint, index: number) => {
    const value = point[metric.key];
    return value === null || !Number.isFinite(value) ? null : { x: samples.length === 1 ? width / 2 : index * width / (samples.length - 1), y: height - (value - minimum) * height / (maximum - minimum) };
  };
  const last = points.at(-1);
  return <View style={s.reportEnvironmentChart}>
    <View style={s.reportLegend}><View style={[s.reportLegendLine, { backgroundColor: metric.color }]} /><Text style={s.reportChartLabel}>{metric.label} ({metric.unit})</Text></View>
    <View style={s.reportChartBody} accessible accessibilityLabel={`${metric.label}. ${samples.map(point => `${reportDate(point.day, true)}: ${reportNumber(point[metric.key])} ${metric.unit}`).join('. ')}`}>
      <View style={s.reportYAxis}>{[maximum, (maximum + minimum) / 2, minimum].map((value, index) => <Text key={index} maxFontSizeMultiplier={1.3} style={s.reportAxisText}>{reportNumber(value)}</Text>)}</View>
      <View style={s.reportChartGrow}>
        <View style={s.reportPlot} onLayout={event => setWidth(event.nativeEvent.layout.width)}>
          {[0, 50, 100].map(top => <View key={top} style={[s.reportGridLine, { top: `${top}%` }]} />)}
          {width > 0 && samples.map((point, index) => {
            const current = position(point, index);
            const previous = index > 0 ? position(samples[index - 1], index - 1) : null;
            if (!current) return null;
            const distance = previous ? Math.hypot(current.x - previous.x, current.y - previous.y) : 0;
            const angle = previous ? Math.atan2(current.y - previous.y, current.x - previous.x) * 180 / Math.PI : 0;
            return <View key={point.day}>
              {previous && <View style={[s.reportChartSegment, { backgroundColor: metric.color, width: distance,
                left: (previous.x + current.x - distance) / 2, top: (previous.y + current.y) / 2 - 1, transform: [{ rotate: `${angle}deg` }] }]} />}
              <View style={[s.reportChartDot, { backgroundColor: metric.color, left: current.x - 2, top: current.y - 2 }]} />
            </View>;
          })}
        </View>
        <View style={s.reportXAxis}>{samples.map(point => <Text key={point.day} maxFontSizeMultiplier={1.3} style={s.reportAxisText}>{reportDate(point.day, true)}</Text>)}</View>
      </View>
    </View>
    <Text style={s.reportChartCaption}>{last ? `${reportDate(last.day, true)}: ${reportNumber(last[metric.key])} ${metric.unit}` : 'Chưa có số đo'}</Text>
  </View>;
}

export function RiskChart({ risks }: { risks: ReportRisk[] }) {
  const maximum = Math.max(1, ...risks.map(day => day.high + day.low));
  return <>
    <View style={s.reportLegends}>
      <View style={s.reportLegend}><View style={[s.reportLegendLine, { backgroundColor: '#d98b1b' }]} /><Text style={s.reportChartLabel}>Nguy cơ cao</Text></View>
      <View style={s.reportLegend}><View style={[s.reportLegendLine, { backgroundColor: '#0b7a54' }]} /><Text style={s.reportChartLabel}>Nguy cơ thấp</Text></View>
    </View>
    <View style={s.reportRiskChart}>
      <View style={s.reportRiskYAxis}><Text style={s.reportAxisText}>{maximum}</Text><Text style={s.reportAxisText}>0</Text></View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.reportRiskBars}>
        {risks.map(day => <View key={day.day} style={s.reportRiskDay} accessible accessibilityLabel={`${reportDate(day.day)}: ${day.high} dự báo nguy cơ cao, ${day.low} dự báo nguy cơ thấp`}>
          <View style={s.reportRiskColumns}>
            {!day.high && !day.low && <Text style={s.reportAxisText}>0</Text>}
            {day.low > 0 && <View style={[s.reportRiskBar, { height: Math.max(5, 80 * day.low / maximum), backgroundColor: '#0b7a54' }]} />}
            {day.high > 0 && <View style={[s.reportRiskBar, { height: Math.max(5, 80 * day.high / maximum), backgroundColor: '#d98b1b' }]} />}
          </View>
          <Text style={s.reportAxisText} maxFontSizeMultiplier={1.3}>{reportDate(day.day, true)}</Text>
        </View>)}
      </ScrollView>
    </View>
  </>;
}
