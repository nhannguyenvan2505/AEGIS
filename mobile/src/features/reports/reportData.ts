import { buildPreviewReport, type ReportData, type ReportInput } from './reportModel';

export type ReportDataSource = { load: (input: ReportInput, token?: string) => Promise<ReportData> };

// Keep the API boundary here: future endpoints should return this normalized report DTO.
export const reportDataSource: ReportDataSource = {
  async load(input) {
    await new Promise<void>(resolve => setTimeout(resolve, 240));
    return buildPreviewReport(input);
  },
};
