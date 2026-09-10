import os
import secrets
from pathlib import Path

from database import db
from sqlalchemy import event


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


def _configure_bootstrap_admin(mapper, connection, target):
    """Eliminate the known default admin password during first-time seeding."""
    del mapper, connection
    if (target.username or "").strip().lower() != "admin" or not target.must_change_password:
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
            raise RuntimeError("DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD must be at least 14 characters.")
        target.password_hash = generate_password_hash(bootstrap)
        return

    if not IS_FROZEN:
        raise RuntimeError(
            "Production provisioning requires DYNAMICPRO_BOOTSTRAP_ADMIN_PASSWORD; "
            "refusing to create a default admin credential."
        )

    credentials_path = Path(USER_DATA_DIR) / "FIRST_RUN_ADMIN.txt"
    try:
        existing_password = None
        if credentials_path.exists():
            for line in credentials_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("password="):
                    existing_password = line.split("=", 1)[1].strip()
                    break
        generated = existing_password or secrets.token_urlsafe(18)
        target.password_hash = generate_password_hash(generated)
        if not existing_password:
            credentials_path.write_text(
                "2TO first-run administrator\n"
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
        raise RuntimeError("Unable to persist first-run administrator credentials securely.") from exc


event.listen(User, "before_insert", _configure_bootstrap_admin)
