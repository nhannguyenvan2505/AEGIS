"""Bộ lọc dùng chung cho nhiều danh sách."""


def like(value):
    """Chuỗi LIKE an toàn: ký tự đặc biệt của LIKE được coi là chữ thường."""
    escaped = value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return '%' + escaped + '%'


def user_clause(alias='u'):
    """Lọc theo tên hoặc email của người dùng (chủ sở hữu); `alias` là bí danh bảng users trong câu SQL."""
    return f'({alias}.full_name LIKE %s OR {alias}.email LIKE %s)'
