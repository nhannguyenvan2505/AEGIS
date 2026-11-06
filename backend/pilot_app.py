"""Shared API-only pilot factory. No web assets, checkpoint load or worker start."""
from pathlib import Path
import sys

PILOT_SOURCE = Path(__file__).resolve().parents[1] / 'frontend'


def create_pilot_app(storage, ai_url='http://127.0.0.1:8000', *,
                     automation_enabled=False, automation_poll_seconds=30,
                     controlled_experiments_enabled=False):
    sys.path.insert(0, str(PILOT_SOURCE))
    from pilot_store import validate_storage
    storage = validate_storage(storage)
    from app import create_app
    app = create_app(dict(DATABASE_PATH=storage/'demo.db', UPLOAD_DIR=storage/'uploads', AI_API_URL=ai_url))
    from pilot_journal import enable_journal
    from pilot_management import enable_management
    from pilot_telemetry import enable_telemetry
    from pilot_followup import enable_followup
    from pilot_episodes import enable_episodes
    from pilot_assessment_versions import enable_assessment_versions
    from pilot_surveillance import enable_surveillance
    from pilot_review import enable_review
    from pilot_timeline import enable_timeline
    from pilot_automation import enable_automation
    enable_journal(app, storage)
    enable_management(app, storage)
    enable_telemetry(app, storage, controlled_experiments_enabled)
    from pilot_forecast import enable_forecast
    enable_forecast(app, storage)
    enable_followup(app, storage)
    enable_episodes(app, storage)
    enable_assessment_versions(app, storage)
    enable_surveillance(app, storage)
    enable_review(app, storage)
    enable_timeline(app, storage)
    enable_automation(app, storage, automation_enabled, automation_poll_seconds)
    app.config['MOBILE_API_MODE'] = 'pilot'
    app.config['MOBILE_CONTROLLED_RAW_WRITE'] = controlled_experiments_enabled

    @app.after_request
    def private_response(response):
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.vary.add('Authorization')
        return response
    return app
