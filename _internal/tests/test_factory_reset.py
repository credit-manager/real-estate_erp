# -*- coding: utf-8 -*-
"""Tests for factory_reset.py - Factory reset engine."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from factory_reset import (
    PRESERVE_TABLES,
    DELETE_ORDER,
    _ALLOWED_TABLES,
    _validate_table_name,
)


class TestPreserveTables:
    """Tests for PRESERVE_TABLES constant."""

    def test_is_set(self):
        assert isinstance(PRESERVE_TABLES, set)

    def test_contains_users(self):
        assert "users" in PRESERVE_TABLES

    def test_contains_roles(self):
        assert "roles" in PRESERVE_TABLES

    def test_contains_system_settings(self):
        assert "system_settings" in PRESERVE_TABLES

    def test_contains_lic_plans(self):
        assert "lic_plans" in PRESERVE_TABLES


class TestDeleteOrder:
    """Tests for DELETE_ORDER constant."""

    def test_is_list(self):
        assert isinstance(DELETE_ORDER, list)

    def test_no_duplicates(self):
        assert len(DELETE_ORDER) == len(set(DELETE_ORDER))

    def test_preserve_tables_not_in_delete_order(self):
        for table in PRESERVE_TABLES:
            assert table not in DELETE_ORDER, f"{table} in both PRESERVE and DELETE"

    def test_delete_order_not_empty(self):
        assert len(DELETE_ORDER) > 100, "Expected at least 100 tables in DELETE_ORDER"


class TestAllowedTables:
    """Tests for _ALLOWED_TABLES constant."""

    def test_contains_all_delete_order(self):
        for table in DELETE_ORDER:
            assert table in _ALLOWED_TABLES

    def test_contains_all_preserve_tables(self):
        for table in PRESERVE_TABLES:
            assert table in _ALLOWED_TABLES


class TestValidateTableName:
    """Tests for _validate_table_name function."""

    def test_valid_table_name(self):
        assert _validate_table_name("users") is None

    def test_valid_delete_order_table(self):
        assert _validate_table_name(DELETE_ORDER[0]) is None

    def test_invalid_table_name_raises(self):
        with pytest.raises(ValueError, match="Unexpected table name"):
            _validate_table_name("DROP TABLE users;--")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            _validate_table_name("")

    def test_sql_injection_attempt(self):
        with pytest.raises(ValueError):
            _validate_table_name("users; DROP TABLE users;--")

    def test_unicode_injection(self):
        with pytest.raises(ValueError):
            _validate_table_name("users\u0000")
