# -*- coding: utf-8 -*-
"""Tests for db_indexes.py - Database index management."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db_indexes import (
    INDEXES,
    _index_name,
    _validate_identifier,
)


class TestIndexes:
    """Tests for INDEXES constant."""

    def test_is_dict(self):
        assert isinstance(INDEXES, dict)

    def test_covers_invoices(self):
        assert "invoices" in INDEXES

    def test_covers_projects(self):
        assert "projects" in INDEXES

    def test_covers_employees(self):
        assert "employees" in INDEXES

    def test_column_lists_are_lists(self):
        for table, cols in INDEXES.items():
            assert isinstance(cols, list), f"Columns for {table} not a list"

    def test_no_empty_column_lists(self):
        for table, cols in INDEXES.items():
            assert len(cols) > 0, f"Empty columns for {table}"


class TestIndexName:
    """Tests for _index_name function."""

    def test_short_name(self):
        name = _index_name("users", ["username"])
        assert name == "ix_users_username"

    def test_long_name_truncated(self):
        long_cols = ["col1", "col2", "col3", "col4", "col5"]
        name = _index_name("a_very_long_table_name_here", long_cols)
        assert len(name) <= 63

    def test_different_inputs_different_names(self):
        name1 = _index_name("table", ["col1"])
        name2 = _index_name("table", ["col2"])
        assert name1 != name2


class TestValidateIdentifier:
    """Tests for _validate_identifier function."""

    def test_valid_identifier(self):
        assert _validate_identifier("users") == "users"

    def test_valid_with_underscore(self):
        assert _validate_identifier("user_roles") == "user_roles"

    def test_valid_starting_with_letter(self):
        assert _validate_identifier("table123") == "table123"

    def test_invalid_starts_with_digit(self):
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            _validate_identifier("1table")

    def test_invalid_contains_space(self):
        with pytest.raises(ValueError):
            _validate_identifier("user roles")

    def test_invalid_contains_semicolon(self):
        with pytest.raises(ValueError):
            _validate_identifier("users; DROP TABLE")

    def test_invalid_contains_dash(self):
        with pytest.raises(ValueError):
            _validate_identifier("user-roles")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            _validate_identifier("")
