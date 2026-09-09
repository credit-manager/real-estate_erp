import os
import secrets
from pathlib import Path

from database import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default="employee")
    is_active = db.Column(db.Boolean, default=True)
    must_change_password = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
            "must_change_password": self.must_change_password,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def _configure_bootstrap_admin(target):
    """Eliminate the known default admin password during first-time seeding.

    Cloud production receives a one-time bootstrap password through an
    environment variable. Frozen desktop builds generate a random password
    and write it once to the user-data directory so the customer can retrieve
    it locally. Development keeps the legacy seed behavior for compatibility.
    """
    if (target.username or "").strip().lower() != "admin":
        return
    if not bool(target.must_change_password):
        return

    try:
        from config import IS_FROZEN, IS_PRODUCTION, USER_DATA_DIR
    except Exception:
        return

    if not IS_PRODUCTION:
        return

    from werkzeug.security import generate_password_hash

    bootstrap = os.environ.get("DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD", "").strip()
    if bootstrap:
        if len(bootstrap) < 14:
            raise RuntimeError(
                "DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD must be at least 14 characters."
            )
        target.password_hash = generate_password_hash(bootstrap)
        return

    if not IS_FROZEN:
        raise RuntimeError(
            "Production provisioning requires DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD; "
            "refusing to create a default admin credential."
        )

    credentials_path = Path(USER_DATA_DIR) / "FIRST_RUN_ADMIN.txt"
    generated = secrets.token_urlsafe(18)
    target.password_hash = generate_password_hash(generated)
    try:
        if credentials_path.exists():
            with credentials_path.open("r", encoding="utf-8") as handle:
                content = handle.read().strip()
            if content:
                return
        credentials_path.write_text(
            "Dynamic Pro ERP first-run administrator\n"
            "username=admin\n"
            f"password={generated}\n"
            "change this password immediately after first login\n",
            encoding="utf-8",
        )
        try:
            os.chmod(credentials_path, 0o600)
        except OSError:
            pass
    except OSError as exc:
        raise RuntimeError(
            "Unable to persist first-run administrator credentials securely."
        ) from exc


from sqlalchemy import event


event.listen(User, "before_insert", _configure_bootstrap_admin)
