# -*- coding: utf-8 -*-
"""Tests for utils/docnum.py - Document number generation."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.docnum import _seq_from_last


class TestSeqFromLast:
    """Tests for _seq_from_last helper function."""

    def test_standard_format(self):
        assert _seq_from_last("INV-2026-0042") == 43

    def test_single_segment(self):
        assert _seq_from_last("42") == 43

    def test_empty_string(self):
        assert _seq_from_last("") == 1  # fallback

    def test_none_value(self):
        assert _seq_from_last(None) == 1

    def test_non_numeric(self):
        assert _seq_from_last("abc") == 1

    def test_custom_fallback(self):
        assert _seq_from_last("", fallback=10) == 10

    def test_large_number(self):
        assert _seq_from_last("ORD-2026-9999") == 10000

    def test_zero(self):
        assert _seq_from_last("INV-0") == 1
