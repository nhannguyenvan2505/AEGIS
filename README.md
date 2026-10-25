# AEGIS

AI and IoT for rice disease monitoring: rice blast, brown spot and sheath blight.

## Repository status

This private repository is being established for a five-person graduation team.
The first commit contains repository setup only. Existing application source has
not yet been imported or verified from a clean clone.

- Local backend: `D:/AEGIS/backend` (Flask; SQLite runtime storage).
- Active AI workspace: `D:/AEGIS-AI` (Flask inference API and YOLO11 tooling).
- Local browser prototype: `D:/AEGIS/frontend`; this is not evidence of a React Native implementation.
- Dataset, model checkpoints, virtual environments and private runtime data are excluded.

These paths describe the current maintainer workspace, not portable installation
instructions. A reproducible setup and selective source import will be reviewed
in follow-up pull requests. Do not upload the entire local workspace.

## Team workflow

Use GitHub Flow: issue -> short-lived branch -> selective commits -> pull request
-> another member reviews -> squash merge -> synchronize local main.
No release or model-performance claim is made by repository initialization.
