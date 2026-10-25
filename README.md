# AEGIS

AI and IoT for rice disease monitoring: rice blast, brown spot and sheath blight.

- backend/: Flask API, Bearer sessions, private analyses/history, farm context and mock warning rules.
- mobile/: Expo / React Native frontend from Minh-Tam-tgd, integrated with authentication, image detection/history and farm create/list APIs.
- AI remains a separate service; datasets, weights and runtime data are excluded.

See [mobile integration and setup](docs/MOBILE_INTEGRATION.md), [upstream attribution](mobile/UPSTREAM.md) and [API contract](backend/docs/API.md).

IoT/prediction screens in mobile still contain labeled demo data. The existing local browser prototype and pilot extensions have not been imported by this PR. A fresh clone needs a separately provisioned AI service for real inference; the isolated HTTP contract test can run without weights.

Use GitHub Flow: issue → branch → selective commits → PR → independent review → squash merge. Workflow documentation is proposed in PR #2; it must be reviewed separately. Do not push directly to main.
