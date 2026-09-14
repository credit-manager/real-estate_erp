# -*- coding: utf-8 -*-
"""Tests for permissions.py - Employee RBAC system."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from permissions import (
    MODULES,
    ACTIONS,
    MODULE_LABELS,
    ADMIN_MODULES,
    _all_true,
    _all_false,
    _view_only,
    _normalize,
)


class TestConstants:
    """Tests for module/action constants."""

    def test_modules_is_list(self):
        assert isinstance(MODULES, list)

    def test_actions_is_list(self):
        assert isinstance(ACTIONS, list)

    def test_actions_are_view_create_edit_delete(self):
        assert ACTIONS == ["view", "create", "edit", "delete"]

    def test_all_modules_have_labels(self):
        for module in MODULES:
            assert module in MODULE_LABELS, f"Missing label for {module}"

    def test_admin_modules_are_subset_of_modules(self):
        for m in ADMIN_MODULES:
            assert m in MODULES, f"Admin module {m} not in MODULES"

    def test_modules_count(self):
        assert len(MODULES) >= 20, "Expected at least 20 modules"

    def test_no_duplicate_modules(self):
        assert len(MODULES) == len(set(MODULES))


class TestAllTrue:
    """Tests for _all_true function."""

    def test_all_modules_all_actions_true(self):
        perms = _all_true()
        for module in MODULES:
            assert module in perms
            for action in ACTIONS:
                assert perms[module][action] is True

    def test_returns_dict(self):
        assert isinstance(_all_true(), dict)


class TestAllFalse:
    """Tests for _all_false function."""

    def test_all_modules_all_actions_false(self):
        perms = _all_false()
        for module in MODULES:
            assert module in perms
            for action in ACTIONS:
                assert perms[module][action] is False


class TestViewOnly:
    """Tests for _view_only function."""

    def test_view_allowed_for_non_admin(self):
        perms = _view_only()
        non_admin = [m for m in MODULES if m not in ADMIN_MODULES]
        for module in non_admin:
            assert perms[module]["view"] is True

    def test_admin_modules_view_denied(self):
        perms = _view_only()
        for module in ADMIN_MODULES:
            assert perms[module]["view"] is False

    def test_create_edit_delete_false(self):
        perms = _view_only()
        for module in MODULES:
            for action in ["create", "edit", "delete"]:
                assert perms[module][action] is False


class TestNormalize:
    """Tests for _normalize function."""

    def test_empty_input(self):
        perms = _normalize({})
        for module in MODULES:
            for action in ACTIONS:
                assert perms[module][action] is False

    def test_none_input(self):
        perms = _normalize(None)
        for module in MODULES:
            for action in ACTIONS:
                assert perms[module][action] is False

    def test_valid_permission(self):
        raw = {"dashboard": {"view": True, "create": True}}
        perms = _normalize(raw)
        assert perms["dashboard"]["view"] is True
        assert perms["dashboard"]["create"] is True
        assert perms["dashboard"]["edit"] is False

    def test_unknown_module_ignored(self):
        raw = {"unknown_module": {"view": True}}
        perms = _normalize(raw)
        assert "unknown_module" not in perms

    def test_unknown_action_ignored(self):
        raw = {"dashboard": {"unknown_action": True}}
        perms = _normalize(raw)
        for action in ACTIONS:
            assert perms["dashboard"][action] is False

    def test_boolean_conversion(self):
        raw = {"dashboard": {"view": 1, "create": "yes"}}
        perms = _normalize(raw)
        assert perms["dashboard"]["view"] is True
        assert perms["dashboard"]["create"] is True
