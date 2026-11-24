"""Bốn loại cảm biến của một ruộng. Dùng chung cho thiết bị và trang ruộng."""

SENSOR_TYPES = ('temperature', 'humidity', 'soil_ph', 'rainfall')
SENSOR_LABELS = {'temperature': 'Nhiệt độ', 'humidity': 'Độ ẩm không khí', 'soil_ph': 'pH đất', 'rainfall': 'Lượng mưa'}


def slots(installed):
    """installed: các sensor_type đang có ở ruộng -> số đã lắp, danh sách còn thiếu."""
    have = {t for t in installed if t in SENSOR_TYPES}
    return {'expected': len(SENSOR_TYPES), 'installed': len(have),
            'missing': [t for t in SENSOR_TYPES if t not in have]}
