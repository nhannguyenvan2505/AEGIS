from app.admin.core import db


def list_alerts(alert_type=None, severity=None, status=None):
    where, params = [], []
    for value, column in ((alert_type, 'a.alert_type'), (severity, 'a.severity'), (status, 'a.status')):
        if value:
            where.append(f'{column}=%s'); params.append(value)
    select = '''a.alert_id id, a.alert_type, a.severity, a.title, a.message, a.status, a.generated_at, a.resolved_at,
                p.external_id plot_id, p.field_name plot_name, u.email owner_email'''
    source = 'alerts a JOIN farm_fields p ON p.field_id=a.field_id JOIN users u ON u.user_id=p.user_id'
    return db.paged(select, source, where, params, 'a.alert_id DESC')


def alert_status(alert_id):
    row = db.one('SELECT status FROM alerts WHERE alert_id=%s', (alert_id,))
    return row['status'] if row else None


def set_alert_status(alert_id, status):
    db.execute('UPDATE alerts SET status=%s, resolved_at=IF(%s="resolved",UTC_TIMESTAMP(),NULL) WHERE alert_id=%s',
               (status, status, alert_id))


def list_notifications(delivery_status=None):
    where, params = [], []
    if delivery_status:
        where.append('n.delivery_status=%s'); params.append(delivery_status)
    select = '''n.notification_id id, n.channel, n.title, n.message, n.delivery_status, n.is_read,
                n.sent_at, n.created_at, u.email user_email'''
    return db.paged(select, 'notifications n JOIN users u ON u.user_id=n.user_id', where, params,
                    'n.notification_id DESC')


def requeue_failed(notification_id):
    return db.execute("UPDATE notifications SET delivery_status='pending' WHERE notification_id=%s "
                      "AND delivery_status='failed'", (notification_id,))[1]
