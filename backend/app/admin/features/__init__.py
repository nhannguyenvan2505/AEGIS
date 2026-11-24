"""Mỗi feature là một thư mục: routes.py (HTTP + phân quyền + audit) và repository.py (SQL).

Thêm feature mới: tạo thư mục có routes.py định nghĩa `bp`, rồi thêm tên vào FEATURES.
"""
from importlib import import_module

FEATURES = ('auth', 'stats', 'users', 'farms', 'devices', 'detections', 'alerts',
            'thresholds', 'knowledge', 'models', 'system')


def register_features(app):
    for name in FEATURES:
        app.register_blueprint(import_module(f'{__name__}.{name}.routes').bp)
