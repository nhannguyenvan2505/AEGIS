import { Directory, File, Paths } from 'expo-file-system';
import * as Print from 'expo-print';
import * as Sharing from 'expo-sharing';
import { buildReportWorkbook, renderReportHtml, reportFileName } from './reportDocument';
import type { ReportData } from './reportModel';

export type ReportFormat = 'pdf' | 'xlsx';
export async function createReportFile(report: ReportData, format: ReportFormat) {
  if (!report.points.length) throw new Error('Chưa có dữ liệu để xuất báo cáo.');
  const directory = new Directory(Paths.cache, 'aegis-reports');
  directory.create({ intermediates: true, idempotent: true });
  const file = new File(directory, reportFileName(report, format));
  if (format === 'pdf') {
    // Expo Go's print module can return a URI outside the experience's FileSystem scope.
    // Write the returned PDF bytes into our own cache rather than reading that URI.
    const result = await Print.printToFileAsync({ html: renderReportHtml(report), width: 595, height: 842, base64: true });
    if (!result.base64 || result.numberOfPages < 1) throw new Error('Chưa tạo được nội dung PDF.');
    file.create({ overwrite: true });
    file.write(result.base64, { encoding: 'base64' });
  } else {
    file.create({ overwrite: true });
    file.write(buildReportWorkbook(report));
  }
  return file.uri;
}
export async function shareReportFile(uri: string, format: ReportFormat) {
  if (!(await Sharing.isAvailableAsync())) throw new Error('Thiết bị chưa mở được bảng lưu tệp. Vui lòng thử lại.');
  await Sharing.shareAsync(uri, {
    mimeType: format === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    UTI: format === 'pdf' ? 'com.adobe.pdf' : 'org.openxmlformats.spreadsheetml.sheet',
    dialogTitle: format === 'pdf' ? 'Xuất báo cáo PDF' : 'Xuất báo cáo Excel',
  });
}
