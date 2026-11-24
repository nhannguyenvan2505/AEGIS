# Field reports

`reportData.ts` is the data boundary. The current source builds local preview reports without calling or writing backend forecasts, diagnoses or alerts. Replace `reportDataSource.load(input, token)` with the future authenticated API adapter; return the `ReportData` DTO and set `source: 'api'`.

- Scope requests by authenticated user, `input.farm.id`, `input.plot.id` and the inclusive ISO date range. Validate that returned records belong to that field and period.
- Use `reportKey(input)` for the returned client request key. The screen rejects stale responses when the field, period or IoT snapshot changes.
- Sensor keys stay `temperature` (°C), `humidity` (% air humidity), `soilPh` (pH soil), `rainfall` (mm accumulated over 24 hours). Missing readings are `null`; zero is a valid value.
- Timestamps are ISO instants; reports display UTC+7. Daily chart points must be no later than `asOf` or the current time.
- Preview data covers the last 30 days. The selected interval is limited to 90 days. Each sensor chart and PDF table shows at most seven representative points.
- Image suspicions, forecast risks and confirmed disease cases are separate concepts. Preview data does not claim disease confirmation.
- `reportDocument.ts` builds a two-page PDF HTML document and a five-sheet OOXML workbook from the same report snapshot. `reportExport.ts` writes files to the app cache and opens the system share sheet only after the user requests export.
- Only PDF export is exposed in the UI. Excel was deferred at the user's request; the workbook helper is retained for a later iteration.
- `components/` contains presentation only. Selecting another field or period changes all report sections and exports together.
