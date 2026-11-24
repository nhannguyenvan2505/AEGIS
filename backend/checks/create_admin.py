"""Tạo (hoặc nâng quyền) tài khoản admin đầu tiên. Mật khẩu nhập qua prompt, không truyền qua tham số dòng lệnh.

    backend\.venv\Scripts\python.exe backend/checks/create_admin.py admin@example.com

Chỉ chạy khi bạn chủ động muốn ghi vào CSDL; script không được gọi tự động ở đâu cả.
"""
import getpass
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from werkzeug.security import generate_password_hash  # noqa: E402

from app.admin.core.db import _connect  # noqa: E402
from app.database_config import settings  # noqa: E402


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    email = sys.argv[1].strip().lower()
    password = getpass.getpass('Mật khẩu (12-128 ký tự): ')
    if not 12 <= len(password) <= 128 or password != getpass.getpass('Nhập lại: '):
        sys.exit('Mật khẩu không hợp lệ hoặc không khớp.')
    conn = _connect(settings())
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT role_id FROM roles WHERE role_name='admin'")
            role = cur.fetchone()
            if role is None:
                sys.exit("Thiếu role 'admin' trong bảng roles.")
            cur.execute('SELECT user_id FROM users WHERE email=%s', (email,))
            existing = cur.fetchone()
            if existing:
                cur.execute("UPDATE users SET role_id=%s, status='active', password_hash=%s WHERE user_id=%s",
                            (role['role_id'], generate_password_hash(password), existing['user_id']))
                print('Đã nâng quyền tài khoản hiện có thành admin.')
            else:
                external = str(uuid.uuid4())
                cur.execute('INSERT INTO users(external_id,role_id,email,username,password_hash) VALUES (%s,%s,%s,%s,%s)',
                            (external, role['role_id'], email, external, generate_password_hash(password)))
                print('Đã tạo tài khoản admin mới.')
        conn.commit()
    finally:
        conn.close()


if __name__ == '__main__':
    main()
