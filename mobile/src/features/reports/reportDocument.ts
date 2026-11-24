import { strToU8, zipSync } from 'fflate';
import { reportConclusion, reportDate, reportMetrics, reportNumber, reportRangeLabel, reportTimestamp, reportTotals, sampleReportPoints, type ReportData } from './reportModel';

export const escapeReportText = (value: unknown) => String(value ?? '').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffe\uffff]/g, '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&apos;');
export const reportFileName = (report: ReportData, extension: 'pdf' | 'xlsx') =>
  `AEGIS-${report.plot.id.replace(/[^a-z0-9-]/gi, '-').slice(0, 48)}-${report.range.start}-${report.range.end}.${extension}`;

export function renderReportHtml(report: ReportData) {
  if (!report.points.length) throw new Error('Chưa có dữ liệu để xuất báo cáo.');
  const totals = reportTotals(report);
  const e = escapeReportText;
  const header = `<div class="brand">AEGIS</div><h1>BÁO CÁO THEO DÕI RUỘNG</h1><p>${e(report.plot.name)} · ${e(report.farm.name)}</p><p>${e(reportRangeLabel(report.range))}</p>`;
  const table = (headers: string[], rows: (string | number | null)[][]) => `<table><thead><tr>${headers.map(value => `<th>${e(value)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${row.map(value => `<td>${e(value ?? '—')}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  const provenance = report.source === 'preview' ? 'Dữ liệu minh họa' : 'Dữ liệu theo dõi của ruộng';
  const footer = (page: number) => `<footer><span>${e(provenance)} · Tổng hợp ${e(reportTimestamp(report.generatedAt))}</span><span>Trang ${page}/2</span></footer>`;
  const points = sampleReportPoints(report.points);
  return `<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8"><title>Báo cáo AEGIS</title><style>
    @page{size:A4;margin:12mm}*{box-sizing:border-box}body{font-family:Arial,sans-serif;color:#24324c;font-size:10pt;margin:0}h1{font-size:17pt;margin:12px 0}h2{font-size:13pt;margin:22px 0 12px}p{line-height:1.6;margin:5px 0}.brand{color:#119f96;font-weight:bold;letter-spacing:3px}.page{height:270mm;position:relative;page-break-after:always;padding-bottom:18mm}.page:last-child{page-break-after:auto}.badge{background:#edf7f4;padding:10px;border-radius:8px;margin:15px 0}.stats{display:flex;gap:12px;margin:18px 0}.stat{flex:1;background:#f2f5f8;padding:14px;border-radius:8px}.stat strong{display:block;font-size:20pt;color:#169e96}table{width:100%;border-collapse:collapse;margin:12px 0;font-size:9pt}th{background:#eaf5f2;text-align:left}td,th{padding:8px;border-bottom:1px solid #dce5ed;vertical-align:top}.muted{color:#7384a0;font-size:9pt}footer{position:absolute;bottom:0;width:100%;display:flex;justify-content:space-between;color:#7c8ba4;font-size:8pt;border-top:1px solid #dce5ed;padding-top:10px}
  </style></head><body><section class="page">${header}<div class="badge">Đến ${e(reportTimestamp(report.asOf!))} · ${e(provenance)}</div>
    <div class="stats"><div class="stat"><strong>${totals.scans}</strong>lần đánh giá ảnh</div><div class="stat"><strong>${totals.suspected}</strong>lần gợi ý triệu chứng</div><div class="stat"><strong>${totals.forecasts}</strong>lần dự báo nguy cơ</div></div>
    <h2>Quan trắc môi trường</h2>${table(['Thời gian (UTC+7)', ...reportMetrics.map(metric => `${metric.label} (${metric.unit})`)], points.map(point => [reportTimestamp(point.observedAt), ...reportMetrics.map(metric => reportNumber(point[metric.key]))]))}
    <p class="muted">Bảng trình bày tối đa 7 mốc đại diện trong kỳ. Lượng mưa tích lũy 24 giờ.</p><h2>Kết luận theo dõi</h2><p>${e(reportConclusion(report))}</p>${footer(1)}</section>
    <section class="page">${header}<h2>Khám lúa bằng AI</h2>${table(['Thời điểm', 'Gợi ý từ ảnh'], report.scans.length ? report.scans.map(scan => [reportTimestamp(scan.at), scan.result === 'suspected' ? 'Nghi ngờ đạo ôn lá' : 'Chưa thấy dấu hiệu rõ']) : [['—', 'Chưa có đánh giá ảnh trong kỳ']])}
    <p class="muted">Bệnh được xác nhận: chưa có xác minh. Số lần AI nghi ngờ không phải số ca nhiễm bệnh.</p><h2>Xu hướng dự báo nguy cơ</h2>${table(['Ngày', 'Nguy cơ cao', 'Nguy cơ thấp'], report.risks.filter(day => day.high || day.low).map(day => [reportDate(day.day), day.high, day.low]))}
    <h2>Tổng hợp cảnh báo</h2>${table(['Thời điểm', 'Nội dung', 'Trạng thái'], report.alerts.length ? report.alerts.map(alert => [reportTimestamp(alert.at), alert.title, alert.state === 'unread' ? 'Chưa đọc' : 'Đã đọc']) : [['—', 'Không có cảnh báo trong kỳ', '—']])}
    <p>${e(reportConclusion(report))}</p><p class="muted">Kết quả AI hỗ trợ theo dõi, không thay thế xác minh thực tế.</p>${footer(2)}</section></body></html>`;
}

type CellValue = string | number | null;
export function buildReportWorkbook(report: ReportData): Uint8Array {
  if (!report.points.length) throw new Error('Chưa có dữ liệu để xuất báo cáo.');
  const totals = reportTotals(report);
  const source = report.source === 'preview' ? 'Dữ liệu minh họa' : 'Dữ liệu theo dõi';
  const metadata: CellValue[][] = [
    ['BÁO CÁO AEGIS'], ['Nông trại', report.farm.name, report.farm.id], ['Ruộng', report.plot.name, report.plot.id],
    ['Kỳ báo cáo', report.range.start, report.range.end], ['Nguồn', source, 'Thời gian UTC+7'],
  ];
  const sheets: { name: string; headers: string[]; rows: CellValue[][] }[] = [
    { name: 'Tổng hợp', headers: ['Chỉ tiêu', 'Giá trị'], rows: [['Đánh giá ảnh', totals.scans], ['Gợi ý triệu chứng', totals.suspected], ['Dự báo nguy cơ', totals.forecasts], ['Cảnh báo', totals.alerts], ['Chưa đọc', totals.unread], ['Bệnh được xác nhận', 'Chưa có xác minh'], ['Kết luận theo dõi', reportConclusion(report)]] },
    { name: 'Quan trắc', headers: ['Thời gian UTC+7', ...reportMetrics.map(metric => `${metric.label} (${metric.unit})`)], rows: report.points.map(point => [reportTimestamp(point.observedAt), ...reportMetrics.map(metric => point[metric.key])]) },
    { name: 'Khám lúa AI', headers: ['Thời gian UTC+7', 'Gợi ý từ ảnh'], rows: report.scans.map(scan => [reportTimestamp(scan.at), scan.result === 'suspected' ? 'Nghi ngờ đạo ôn lá' : 'Chưa thấy dấu hiệu rõ']) },
    { name: 'Dự báo', headers: ['Ngày', 'Nguy cơ cao', 'Nguy cơ thấp'], rows: report.risks.map(day => [reportDate(day.day), day.high, day.low]) },
    { name: 'Cảnh báo', headers: ['Thời gian UTC+7', 'Nội dung', 'Trạng thái'], rows: report.alerts.map(alert => [reportTimestamp(alert.at), alert.title, alert.state === 'unread' ? 'Chưa đọc' : 'Đã đọc']) },
  ];
  const xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
  const ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main';
  const rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships';
  const files: Record<string, Uint8Array> = {};
  sheets.forEach((sheet, index) => {
    const rows = [...metadata, sheet.headers, ...sheet.rows];
    // Explicit inline strings keep user-supplied names as text, including names starting with '='.
    const data = rows.map((row, rowIndex) => `<row r="${rowIndex + 1}">${row.map((value, column) => {
      const reference = `${String.fromCharCode(65 + column)}${rowIndex + 1}`;
      const style = rowIndex === 0 || rowIndex === 5 ? ' s="1"' : '';
      if (value === null || value === undefined) return `<c r="${reference}"/>`;
      return typeof value === 'number' && Number.isFinite(value)
        ? `<c r="${reference}"${style}><v>${value}</v></c>`
        : `<c r="${reference}" t="inlineStr"${style}><is><t xml:space="preserve">${escapeReportText(value)}</t></is></c>`;
    }).join('')}</row>`).join('');
    files[`xl/worksheets/sheet${index + 1}.xml`] = strToU8(`${xml}<worksheet xmlns="${ns}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="6" topLeftCell="A7" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="1" width="26" customWidth="1"/><col min="2" max="5" width="24" customWidth="1"/></cols><sheetData>${data}</sheetData></worksheet>`);
  });
  files['[Content_Types].xml'] = strToU8(`${xml}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>${sheets.map((_, index) => `<Override PartName="/xl/worksheets/sheet${index + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('')}</Types>`);
  files['_rels/.rels'] = strToU8(`${xml}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>`);
  files['xl/workbook.xml'] = strToU8(`${xml}<workbook xmlns="${ns}" xmlns:r="${rel}"><sheets>${sheets.map((sheet, index) => `<sheet name="${escapeReportText(sheet.name)}" sheetId="${index + 1}" r:id="rId${index + 1}"/>`).join('')}</sheets></workbook>`);
  files['xl/_rels/workbook.xml.rels'] = strToU8(`${xml}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${sheets.map((_, index) => `<Relationship Id="rId${index + 1}" Type="${rel}/worksheet" Target="worksheets/sheet${index + 1}.xml"/>`).join('')}<Relationship Id="rId${sheets.length + 1}" Type="${rel}/styles" Target="styles.xml"/></Relationships>`);
  files['xl/styles.xml'] = strToU8(`${xml}<styleSheet xmlns="${ns}"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF159F96"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>`);
  return zipSync(files, { level: 6 });
}
