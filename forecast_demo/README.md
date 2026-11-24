# Portable synthetic forecast demo runtime

T09 (2026-11-08) adds the separately pinned `weather_bundle/` and
`runtime/weather_forecast.py` for stored raw hourly sources and scheduler jobs.
FM-03 uses temperature/RH and crop age with 120 complete available numeric hours;
whole-hour wetness may be null. Legacy demo scenarios and directly supplied
hourly/source histories retain FM-02. Both models use synthetic data and
uncalibrated scores. See [FM-03 API and operation](../backend/docs/RAW_WEATHER_FORECAST_T09.md)
and [validation evidence](../docs/RAW_FORECAST_VALIDATION_T09.md).

This folder is a small, self-contained forecast runtime for the AEGIS mobile
midterm. It lets a teammate clone the AEGIS repository and run the same
source → synthetic hourly input → Logistic Regression → persisted forecast
flow without a sibling `AEGIS-AI` workspace.

## What is included

- The inference modules vendored from `AEGIS-AI/temporal_warning`:
  `pipeline.py`, `feature_preparation.py`, `synthetic_forecast_data.py`,
  `cluster_partition.py`, `synthetic_baseline.py`, and
  `serve_synthetic_forecast.py`.
- The trained FM-02 Logistic Regression `baseline.joblib`, its manifest and
  the FM-01 synthetic ready/insufficient fixtures needed by this demo.
- No YOLO checkpoint, image dataset, field data, or production credential.

The model was fitted on FM-01 synthetic data only. Its manifest pins the model,
feature contract, source, training partition and runtime versions. The model
score is uncalibrated; the simulated 72-hour event is not a field disease
diagnosis. The binary model is a trusted project artifact: inspect the source
and keep the SHA-256 checks in the worker before loading joblib.

## Python environment

Use Python 3.11. Install these packages in `forecast_demo/.venv`; the separate
Backend environment under `backend/.venv` needs the packages in
`backend/requirements.txt`.

```powershell
py -3.11 -m venv forecast_demo\.venv
& .\forecast_demo\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\forecast_demo\.venv\Scripts\python.exe -m pip install -r forecast_demo\requirements.txt
py -3.11 -m venv backend\.venv
& .\backend\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

## Start the shared demo

From the repository root, launch the pilot API and model worker. Enter the
demo account password in the terminal. Keep this process open:

```powershell
& .\backend\.venv\Scripts\python.exe -X utf8 -B tools\forecast_demo.py --model-python .\forecast_demo\.venv\Scripts\python.exe
```

The default account is `midterm@example.test`. Use the same password on mobile.
The persistent local demo store is `pilot_data/forecast-midterm`; it is ignored
by Git. The launcher prints two seeded plots/seasons and saves IDs in
`ready.json`. Ctrl+C stops both local services and keeps the store.

## Start Android mobile

In a second PowerShell window, connect an Android emulator or phone with ADB.
Forward the API port to the computer's loopback, then start Expo with that URL:

```powershell
adb reverse tcp:5000 tcp:5000
$env:EXPO_PUBLIC_API_URL='http://127.0.0.1:5000/api'
Set-Location mobile
npm ci
npm start
```

Open the Expo app on the connected device and sign in with the demo credentials.
The home page shows both seeded seasons. Under **Dự báo**, select a plot and
season, inspect its hourly synthetic source, then choose **Dự báo từ nguồn của
mùa vụ**. To see the missing-data path and recovery, follow the
[forecast runbook](../docs/FORECAST_MVP_MIDTERM_20261105.md).

This launcher starts the forecast pilot only. Image recognition requires its
separate AI API and V4 checkpoint; it is not needed for the midterm forecast
flow. Expo export or TypeScript/HTTP checks are not a substitute for testing
login and navigation on the member's device.
