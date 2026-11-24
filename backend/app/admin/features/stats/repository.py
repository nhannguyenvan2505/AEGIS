from app.admin.core import db


def _count(sql):
    return db.one(sql)['n']


def overview():
    return dict(
        users={'total': _count('SELECT COUNT(*) n FROM users'),
               'active_7d': _count('SELECT COUNT(*) n FROM users WHERE last_login_at>=UTC_TIMESTAMP()-INTERVAL 7 DAY')},
        farms=_count('SELECT COUNT(*) n FROM farms'),
        plots=_count('SELECT COUNT(*) n FROM farm_fields'),
        devices={'online': _count("SELECT COUNT(*) n FROM iot_devices WHERE status='online'"),
                 'offline': _count("SELECT COUNT(*) n FROM iot_devices WHERE status='offline'"),
                 'total': _count('SELECT COUNT(*) n FROM iot_devices')},
        detections_today=_count("SELECT COUNT(*) n FROM analysis_runs "
                                "WHERE created_at>=DATE_FORMAT(UTC_DATE(),'%%Y-%%m-%%d')"),
        alerts_open=_count("SELECT COUNT(*) n FROM alerts WHERE status='open'"),
    )


def detections_by_day(days):
    return db.query('''SELECT SUBSTRING(created_at,1,10) day, COUNT(*) count FROM analysis_runs
                       WHERE created_at>=DATE_FORMAT(UTC_DATE()-INTERVAL %s DAY,'%%Y-%%m-%%d')
                       GROUP BY day ORDER BY day''', (days,))


def disease_distribution(days):
    return db.query('''SELECT disease_label disease, COUNT(*) count FROM disease_detections
                       WHERE created_at>=UTC_TIMESTAMP()-INTERVAL %s DAY GROUP BY disease_label
                       ORDER BY count DESC''', (days,))


def users_by_week(days):
    return db.query('''SELECT DATE_FORMAT(created_at,'%%x-W%%v') week, COUNT(*) count FROM users
                       WHERE created_at>=UTC_TIMESTAMP()-INTERVAL %s DAY GROUP BY week ORDER BY week''', (days,))


def risk_distribution(days):
    return db.query('''SELECT risk_level, COUNT(*) count FROM risk_predictions
                       WHERE predicted_at>=UTC_TIMESTAMP()-INTERVAL %s DAY GROUP BY risk_level''', (days,))
