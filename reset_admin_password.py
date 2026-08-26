# -*- coding: utf-8 -*-
"""إعادة تعيين كلمة مرور حساب مدير النظام (admin).

الاستخدام:
    python reset_admin_password.py
    python reset_admin_password.py --password MyNewPass123
    python reset_admin_password.py --random   # توليد كلمة مرور عشوائية قوية
"""
import argparse
import sys

from werkzeug.security import generate_password_hash

from app import create_app
from database import db
from models import User


def main():
    parser = argparse.ArgumentParser(description="Reset the admin password")
    parser.add_argument("--password", "-p", default=None,
                        help="New password (if omitted, prompts interactively)")
    parser.add_argument("--random", action="store_true",
                        help="Generate a strong random password and print it once")
    args = parser.parse_args()

    password = args.password
    if args.random:
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        password = "".join(secrets.choice(alphabet) for _ in range(14))
        print("Generated random password (save it now):")
        print(password)
    elif not password:
        import getpass
        password = getpass.getpass("Enter new admin password (min 6 chars): ")

    if (not args.random
            and (len(password) < 8
                 or not any(c.isalpha() for c in password)
                 or not any(c.isdigit() for c in password))):
        print("Password must be at least 8 characters with letters and digits.")
        sys.exit(1)

    app = create_app()
    with app.app_context():
        admin = User.query.filter_by(username="admin", role="admin").first()
        if not admin:
            print("No admin account found. The app creates one automatically on first start.")
            sys.exit(1)
        admin.password_hash = generate_password_hash(password)
        admin.must_change_password = False
        db.session.commit()
        print(f"Password reset OK for user '{admin.username}'.")


if __name__ == "__main__":
    main()
