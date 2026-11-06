# AEGIS

AI and IoT for rice disease monitoring: rice blast, brown spot and sheath blight.

- backend/: Flask API, Bearer sessions, private analyses/history, farm context and mock warning rules.
- mobile/: Expo / React Native frontend from Minh-Tam-tgd, integrated with authentication, image detection/history, farm create/list and opt-in pilot follow-up APIs.
- The midterm forecast demo includes a small, synthetic CPU model bundle under `forecast_demo/`; the YOLO image service, datasets and image weights remain separately provisioned.

**Clone and run the Android forecast demo:** start with
[the portable demo guide](forecast_demo/README.md). It seeds one local Backend
store and connects the Expo app to the same computer through ADB reverse.

Current handoff (07/11/2026): [capabilities and evidence index](docs/CURRENT_HANDOFF.md),
[forecast runbook](docs/FORECAST_MVP_MIDTERM_20261105.md) and [AI/Backend runbook](docs/CURRENT_RUNBOOK.md). They distinguish core/mobile,
local opt-in pilot extensions, offline temporal research and dated artifacts.
The portable synthetic forecast package and its required pilot source are included
in this branch. Follow its guide for a fresh clone; recognition still requires a
separately provisioned AI API and YOLO checkpoint.

Updated 04/11/2026: [screen/API handoff and current verification](docs/BE03_MOBILE_API_HANDOFF_20261104.md).
The alerts route uses pilot follow-up after login; dashboard/data/recommendation
screens retain demo content. Native acceptance remains pending.

See [mobile integration and setup](docs/MOBILE_INTEGRATION.md), [upstream attribution](mobile/UPSTREAM.md) and [API contract](backend/docs/API.md).

IoT readings and forecasts in the midterm flow are synthetic. The package guide
does not claim field validation, image recognition readiness, or device acceptance.

Use GitHub Flow: issue → branch → selective commits → PR → independent review → squash merge. Workflow documentation is proposed in PR #2; it must be reviewed separately. Do not push directly to main.
