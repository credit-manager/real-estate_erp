# -*- coding: utf-8 -*-
"""Tests for security/rbac.py - Master control center RBAC."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from security.rbac import (
    PERMISSION_CATALOG,
    SYSTEM_ROLES,
    _ROLE_PERMISSIONS,
    _all_codes,
    permitted,
)


class TestPermissionCatalog:
    """Tests for PERMISSION_CATALOG constant."""

    def test_is_list(self):
        assert isinstance(PERMISSION_CATALOG, list)

    def test_each_entry_is_tuple(self):
        for entry in PERMISSION_CATALOG:
            assert isinstance(entry, tuple)
            assert len(entry) == 2

    def test_codes_are_dotted_notation(self):
        for code, desc in PERMISSION_CATALOG:
            assert "." in code, f"Code {code} missing dot notation"
            assert isinstance(desc, str)

    def test_no_duplicate_codes(self):
        codes = [c for c, _ in PERMISSION_CATALOG]
        assert len(codes) == len(set(codes))


class TestSystemRoles:
    """Tests for SYSTEM_ROLES constant."""

    def test_has_required_roles(self):
        assert "super_admin" in SYSTEM_ROLES
        assert "admin" in SYSTEM_ROLES
        assert "support" in SYSTEM_ROLES
        assert "sales" in SYSTEM_ROLES

    def test_descriptions_are_strings(self):
        for name, desc in SYSTEM_ROLES.items():
            assert isinstance(desc, str), f"Role {name} has non-string description"


class TestAllCodes:
    """Tests for _all_codes function."""

    def test_returns_list(self):
        result = _all_codes()
        assert isinstance(result, list)

    def test_contains_all_catalog_codes(self):
        codes = _all_codes()
        for code, _ in PERMISSION_CATALOG:
            assert code in codes

    def test_length_matches_catalog(self):
        assert len(_all_codes()) == len(PERMISSION_CATALOG)


class TestRolePermissions:
    """Tests for _ROLE_PERMISSIONS dictionary."""

    def test_admin_has_no_restrictions(self):
        assert _ROLE_PERMISSIONS["admin"] is not None
        assert isinstance(_ROLE_PERMISSIONS["admin"], list)

    def test_support_has_view_permissions(self):
        support_perms = _ROLE_PERMISSIONS["support"]
        assert "dashboard.view" in support_perms
        assert "companies.view" in support_perms

    def test_sales_has_companies_permissions(self):
        sales_perms = _ROLE_PERMISSIONS["sales"]
        assert "companies.view" in sales_perms
        assert "companies.create" in sales_perms

    def test_all_role_permissions_are_valid_codes(self):
        valid_codes = set(_all_codes())
        for role, perms in _ROLE_PERMISSIONS.items():
            if perms is None:
                continue  # super_admin has None (all permissions)
            for perm in perms:
                assert perm in valid_codes, f"Invalid code {perm} in role {role}"


class TestPermitted:
    """Tests for permitted function."""

    def test_single_permission_present(self):
        perms = {"dashboard.view", "companies.view"}
        assert permitted(perms, "dashboard.view") is True

    def test_single_permission_absent(self):
        perms = {"dashboard.view"}
        assert permitted(perms, "companies.view") is False

    def test_all_permissions_required(self):
        perms = {"dashboard.view", "companies.view"}
        assert permitted(perms, ["dashboard.view", "companies.view"]) is True

    def test_missing_permission(self):
        perms = {"dashboard.view"}
        assert permitted(perms, ["dashboard.view", "companies.view"]) is False

    def test_empty_permission_set(self):
        assert permitted(set(), "dashboard.view") is False

    def test_empty_required_list(self):
        assert permitted({"dashboard.view"}, []) is True
