import { useState } from 'react';
import { Pressable, Text, TextInput, View } from 'react-native';
import { Icon } from '../../../components/Design';
import { s } from '../../../styles/generated/styles';
import { ProfileButton, ProfileNotice, profileColors } from '../../profile/components/ProfileUI';
import { parseReportDay, reportDate, reportDay, shiftReportDay, validateReportRange, type ReportRange } from '../reportModel';

export function ReportPeriodPicker({ range, onApply }: { range: ReportRange; onApply: (range: ReportRange) => void }) {
  const [start, setStart] = useState(reportDate(range.start));
  const [end, setEnd] = useState(reportDate(range.end));
  const [error, setError] = useState('');
  function apply() {
    const startDay = parseReportDay(start);
    const endDay = parseReportDay(end);
    if (!startDay || !endDay) { setError('Nhập ngày hợp lệ theo định dạng ngày/tháng/năm.'); return; }
    const next = { start: startDay, end: endDay };
    const problem = validateReportRange(next);
    if (problem) { setError(problem); return; }
    onApply(next);
  }
  return <>
    <Text style={s.reportMuted}>Chọn nhanh hoặc nhập khoảng ngày cần xem.</Text>
    <View style={s.reportPeriodPresets}>{[4, 7, 30].map(days => <Pressable key={days} accessibilityRole="button" accessibilityLabel={`${days} ngày gần nhất`}
      onPress={() => onApply({ start: shiftReportDay(reportDay(), 1 - days), end: reportDay() })} style={({ pressed }) => [s.reportPeriodChip, pressed && s.profilePressed]}>
      <Text style={s.reportPeriodChipText}>{days} ngày</Text>
    </Pressable>)}</View>
    <View><Text style={s.profileFieldLabel}>Từ ngày</Text><View style={s.profileInputRow}><Icon name="calendar" size={18} color={profileColors.muted} />
      <TextInput testID="report-period-start" accessibilityLabel="Ngày bắt đầu" value={start} placeholder="dd/mm/yyyy" maxLength={10} autoCorrect={false} style={s.profileInput} onChangeText={value => { setStart(value); setError(''); }} />
    </View></View>
    <View><Text style={s.profileFieldLabel}>Đến ngày</Text><View style={s.profileInputRow}><Icon name="calendar" size={18} color={profileColors.muted} />
      <TextInput testID="report-period-end" accessibilityLabel="Ngày kết thúc" value={end} placeholder="dd/mm/yyyy" maxLength={10} autoCorrect={false} style={s.profileInput} onChangeText={value => { setEnd(value); setError(''); }} />
    </View></View>
    {!!error && <ProfileNotice message={error} />}
    <Text style={s.reportMuted}>Dữ liệu minh họa có trong 30 ngày gần nhất. Mỗi kỳ tối đa 90 ngày.</Text>
    <ProfileButton title="Xem báo cáo" testID="report-apply-period" onPress={apply} />
  </>;
}
