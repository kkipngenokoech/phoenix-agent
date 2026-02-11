"""Tests for utility functions."""

import pytest
from src.utils import calculate_shipping_cost, format_user_display, categorize_value


class TestShippingCost:
    def test_light_package(self):
        cost = calculate_shipping_cost(
            weight=0.5, length=10, width=10, height=10,
            origin_zip="10001", dest_zip="10002",
            is_fragile=False, is_express=False,
            is_insured=False, insurance_value=0,
        )
        assert cost > 0
        assert isinstance(cost, float)

    def test_heavy_package(self):
        cost = calculate_shipping_cost(
            weight=60, length=30, width=30, height=30,
            origin_zip="10001", dest_zip="90210",
            is_fragile=False, is_express=False,
            is_insured=False, insurance_value=0,
        )
        assert cost > 89.0  # base for 50+ lbs

    def test_express_shipping(self):
        regular = calculate_shipping_cost(
            weight=5, length=10, width=10, height=10,
            origin_zip="10001", dest_zip="10002",
            is_fragile=False, is_express=False,
            is_insured=False, insurance_value=0,
        )
        express = calculate_shipping_cost(
            weight=5, length=10, width=10, height=10,
            origin_zip="10001", dest_zip="10002",
            is_fragile=False, is_express=True,
            is_insured=False, insurance_value=0,
        )
        assert express > regular

    def test_fragile_surcharge(self):
        normal = calculate_shipping_cost(
            weight=2, length=10, width=10, height=10,
            origin_zip="10001", dest_zip="10002",
            is_fragile=False, is_express=False,
            is_insured=False, insurance_value=0,
        )
        fragile = calculate_shipping_cost(
            weight=2, length=10, width=10, height=10,
            origin_zip="10001", dest_zip="10002",
            is_fragile=True, is_express=False,
            is_insured=False, insurance_value=0,
        )
        assert abs(fragile - (normal + 7.50)) < 0.01


class TestFormatUserDisplay:
    def test_basic_format(self):
        user = {"username": "alice", "email": "alice@example.com", "age": 30}
        result = format_user_display(user)
        assert "alice" in result

    def test_email_masking(self):
        user = {"username": "bob", "email": "bob@example.com"}
        result = format_user_display(user, include_phone=False, include_address=False, include_age=False)
        assert "@" in result

    def test_exclude_fields(self):
        user = {"username": "carol", "email": "c@d.com", "phone": "1234567890"}
        result = format_user_display(user, include_email=False, include_phone=False,
                                      include_address=False, include_age=False)
        assert "Email" not in result
        assert "Phone" not in result


class TestCategorizeValue:
    def test_critical(self):
        assert categorize_value(95) == "critical"

    def test_high(self):
        assert categorize_value(75) == "high"

    def test_medium(self):
        assert categorize_value(50) == "medium"

    def test_low(self):
        assert categorize_value(15) == "low"

    def test_minimal(self):
        assert categorize_value(5) == "minimal"

    def test_none(self):
        assert categorize_value(None) == "unknown"

    def test_negative(self):
        assert categorize_value(-5) == "negative"

    def test_custom_thresholds(self):
        thresholds = {"critical": 100, "high": 80, "medium": 50, "low": 20}
        assert categorize_value(85, thresholds) == "high"
