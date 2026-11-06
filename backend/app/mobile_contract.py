"""Authenticated surface discovery; capabilities are not AI health checks."""
from flask import Blueprint, current_app, jsonify
from .auth import require_auth

CONTRACT_VERSION = 'aegis-mobile-followup-v1'


def enable_mobile_contract(app):
    bp = Blueprint('mobile_contract', __name__, url_prefix='/api/mobile')

    @bp.after_request
    def private(response):
        response.headers['Cache-Control'] = 'private, no-store'
        response.vary.add('Authorization')
        return response

    @bp.get('/capabilities')
    @require_auth
    def capabilities():
        pilot = current_app.config.get('MOBILE_API_MODE') == 'pilot'
        runner = current_app.extensions.get('mock_automation')
        return jsonify(success=True, contract_version=CONTRACT_VERSION,
            mode='pilot' if pilot else 'core',
            follow_up=dict(available=pilot, source='mock',
                unavailable_reason=None if pilot else 'requires_pilot_entrypoint',
                disease_confirmed=False, training_approved=False),
            controlled_experiment_raw_write=bool(current_app.config.get('MOBILE_CONTROLLED_RAW_WRITE', False)),
            mock_automation_process_enabled=bool(runner and runner.enabled),
            image_detection=dict(api_available=True, service_status='not_checked'),
            forecast=dict(api_available=pilot, source='synthetic', horizon_hours=72,
                service_status='not_checked', field_validated=False))

    app.register_blueprint(bp)
