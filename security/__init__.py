# -*- coding: utf-8 -*-
"""Security package (Phase 1 + Phase 6).

Master authentication, RBAC roles/permissions, JWT, TOTP 2FA,
sessions, login monitoring, emergency controls.

Phase 1 (implemented now):
    - RBAC models (MasterRole / MasterPermission / MasterSession / MFA / audit)
    - permission catalog + system role seeding
    - ``permission_required`` decorator (dot-notation permission gate)
    - JWT access/refresh tokens bound to revocable sessions
    - TOTP 2FA (pyotp) enrollment / verification / recovery codes
"""
from security.models import (  # noqa: F401
    MasterRole,
    MasterPermission,
    MasterRolePermission,
    MasterUserRole,
    MasterSession,
    MasterTwoFactor,
    MasterAuditLog,
    ModuleCatalog,
    CompanyModule,
)
from security.rbac import (  # noqa: F401
    has_permission,
    permitted,
    permission_required,
    seed_roles_and_permissions,
    user_permissions,
)
from security.tokens import (  # noqa: F401
    decode_token,
    issue_token_pair,
    refresh_access_token,
)
from security.two_factor import (  # noqa: F401
    disable,
    enroll,
    generate_recovery_codes,
    is_enabled,
    provisioning_uri,
    require_two_factor,
    verify_code,
    verify_recovery_code,
)

__all__ = [
    "MasterRole", "MasterPermission", "MasterSession", "MasterTwoFactor",
    "MasterAuditLog",
    "has_permission", "permitted", "permission_required",
    "seed_roles_and_permissions", "user_permissions",
    "decode_token", "issue_token_pair", "refresh_access_token",
    "disable", "enroll", "generate_recovery_codes", "is_enabled",
    "provisioning_uri", "require_two_factor", "verify_code",
    "verify_recovery_code",
]
