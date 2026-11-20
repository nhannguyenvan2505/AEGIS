# AEGIS

**Frontend midterm handoff:** follow [the team quickstart](docs/MIDTERM_TEAM_QUICKSTART.md) for setup, private model download, hybrid databases and demo launch. See [checkout verification](docs/MIDTERM_HANDOFF_VERIFICATION.md) for what was exercised.

Database update 09/11/2026: core/mobile/pilot now default to MySQL with MongoDB telemetry and inference logs. Start Docker databases before the API; see [hybrid database runbook](docs/HYBRID_DATABASE_RUNBOOK.md). Existing runtime SQLite data has been migrated and retained as recovery sources.

AI and IoT for rice disease monitoring: rice blast, brown spot and sheath blight.

- backend/: Flask API, Bearer sessions, private analyses/history, farm context and mock warning rules.
- mobile/: Expo / React Native frontend from Minh-Tam-tgd, integrated with authentication, image detection/history, farm create/list and opt-in pilot follow-up APIs.
- The repo includes the mobile/API pilot, browser prototype, synthetic IoT tools,
  and a portable forecast model. The YOLO API source is under `ai_service/api/`;
  its checkpoint and image datasets remain separately provisioned.

**Clone and run the project demos:** start with [the team handoff](CLONE_DEMO.md).
For Android forecast-only setup, see [the portable forecast guide](forecast_demo/README.md).

Current handoff (07/11/2026): [capabilities and evidence index](docs/CURRENT_HANDOFF.md),
[forecast runbook](docs/FORECAST_MVP_MIDTERM_20261105.md) and [AI/Backend runbook](docs/CURRENT_RUNBOOK.md). They distinguish core/mobile,
local opt-in pilot extensions, offline temporal research and dated artifacts.
The portable synthetic forecast package, browser pilot and simulator source are
included in this branch. The AI API source is included; real recognition still
requires the separately provisioned V4 checkpoint.

Updated 04/11/2026: [screen/API handoff and current verification](docs/BE03_MOBILE_API_HANDOFF_20261104.md).
The alerts route uses pilot follow-up after login; dashboard/data/recommendation
screens retain demo content. Native acceptance remains pending.

See [mobile integration and setup](docs/MOBILE_INTEGRATION.md), [upstream attribution](mobile/UPSTREAM.md) and [API contract](backend/docs/API.md).

IoT readings and forecasts in the midterm flow are synthetic. See the clone guide
for model/data limits; field validation and device acceptance remain pending.

Team workflow: issue → task branch → PR into `develop` → independent review → release into `main`. See [CONTRIBUTING.md](CONTRIBUTING.md) for team rules and [GitHub setup](docs/GITHUB_TEAM_SETUP.md) for activation status. Do not push directly to shared branches.

==================

# 1. Bật MySQL

.\backend\.venv\Scripts\python.exe backend/database/setup_native_mysql.py

# 2. Chạy backend

.\backend\.venv\Scripts\python.exe -u -X utf8 -B backend/serve_mobile.py --pilot-dir pilot_data/forecast-midterm
