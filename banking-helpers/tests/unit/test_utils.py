"""Unit tests for banking_helpers.utils module."""

import warnings
from datetime import datetime

import pytest
from banking_helpers.utils import (
    find_all_columns,
    format_date,
    match_category_pattern,
    match_first_pattern_text,
    normalize_combined_text,
    parse_amount,
    parse_date,
)


class TestMatchCategoryPattern:
    """Tests for match_category_pattern function."""

    @pytest.mark.parametrize(
        "text,patterns,expected",
        [
            ("REWE MARKT GMBH", {"rewe|edeka|aldi": "groceries"}, "groceries"),
            ("Spotify AB", {"spotify": "fun"}, "fun"),
            ("SPOTIFY AB", {"spotify": "fun"}, "fun"),
            (
                "REWE MARKT",
                {"rewe|edeka": "groceries", "rewe|amazon": "shopping"},
                "groceries",
            ),
            ("UNKNOWN STORE", {"rewe|edeka": "groceries"}, ""),
            ("ANY TEXT", {}, ""),
            (
                "AMAZON PRIME VIDEO",
                {"amazon.*video": "streaming", "spotify|netflix": "streaming"},
                "streaming",
            ),
        ],
    )
    def test_match_pattern(self, text, patterns, expected):
        """Test pattern matching with various inputs."""
        assert match_category_pattern(text, patterns) == expected

    def test_invalid_regex_pattern_warning(self):
        """Test that invalid regex patterns trigger warnings."""
        patterns = {"[unclosed": "category"}
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = match_category_pattern("ANY TEXT", patterns)
            assert result == ""
            assert len(w) == 1
            assert issubclass(w[0].category, SyntaxWarning)
            assert "Invalid regex pattern" in str(w[0].message)

    def test_multiple_patterns_partial_invalid(self):
        """Test that partial invalid patterns skip and continue matching."""
        patterns = {
            "[invalid": "skip",
            "rewe": "groceries",
        }
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = match_category_pattern("REWE MARKT", patterns)
            assert result == "groceries"


class TestParseDate:
    """Tests for parse_date function."""

    @pytest.mark.parametrize(
        "date_str,format_str,expected_day,expected_month,expected_year",
        [
            ("15.03.26", "DD.MM.YY", 15, 3, 2026),
            ("03/15/2026", "MM/DD/YYYY", 15, 3, 2026),
            ("2026-03-15", None, 15, 3, 2026),
            ("  15.03.2026  ", "DD.MM.YYYY", 15, 3, 2026),
        ],
    )
    def test_parse_date_formats(
        self, date_str, format_str, expected_day, expected_month, expected_year
    ):
        """Test parsing various date formats."""
        result = parse_date(date_str, format_str)
        assert result.day == expected_day
        assert result.month == expected_month
        assert result.year == expected_year

    def test_parse_invalid_date_raises_error(self):
        """Test that invalid date raises ValueError."""
        with pytest.raises(ValueError):
            parse_date("99.99.9999", "DD.MM.YYYY")


class TestFormatDate:
    """Tests for format_date function."""

    @pytest.mark.parametrize(
        "dt,format_str,expected",
        [
            (datetime(2026, 3, 15), "DD.MM.YY", "15.03.26"),
            (datetime(2026, 3, 15), "YYYY-MM-DD", "2026-03-15"),
            (datetime(2026, 3, 15), "MM/DD/YYYY", "03/15/2026"),
        ],
    )
    def test_format_date_outputs(self, dt, format_str, expected):
        """Test formatting dates to various outputs."""
        assert format_date(dt, format_str) == expected


class TestParseAmount:
    """Tests for parse_amount function."""

    @pytest.mark.parametrize(
        "amount_str,positive_is,decimal_sep,expected",
        [
            ("100.50", "debit", ".", -100.50),
            ("100.50", "credit", ".", 100.50),
            ("€100.50", "debit", ".", -100.50),
            ("$100.50", "debit", ".", -100.50),
            ("1.234,56", "debit", ",", -1234.56),
            ("100,50", "debit", ",", -100.50),
            ("  100.50  ", "debit", ".", -100.50),
            ("-100.50", "credit", ".", -100.50),
            ("0", "debit", ".", 0.0),
        ],
    )
    def test_parse_amount_values(
        self, amount_str, positive_is, decimal_sep, expected
    ):
        """Test parsing various amount formats."""
        assert parse_amount(amount_str, positive_is, decimal_sep) == expected

    def test_parse_amount_invalid_raises_error(self):
        """Test that invalid amount raises ValueError."""
        with pytest.raises(ValueError):
            parse_amount("not-a-number", "debit")


class TestMatchFirstPatternText:
    """Tests for match_first_pattern_text function."""

    @pytest.mark.parametrize(
        "text,patterns,expected",
        [
            # Returns the matched fragment, lowercased
            ("REWE MARKT GMBH 12345", {"rewe|edeka": "groceries"}, "rewe"),
            ("EDEKA CENTER BERLIN", {"rewe|edeka": "groceries"}, "edeka"),
            # Multi-word pattern returns full match
            (
                "AMAZON PRIME VIDEO SUBSCRIPTION",
                {
                    "amazon prime video": "fun",
                    "amazon": "household",
                },
                "amazon prime video",
            ),
            # Alternation: first matching branch returned
            (
                "SPOTIFY SUBSCRIPTION",
                {"spotify|netflix": "fun"},
                "spotify",
            ),
            # No match returns empty string
            ("UNKNOWN STORE", {"rewe|edeka": "groceries"}, ""),
            # Empty patterns returns empty string
            ("ANY TEXT", {}, ""),
        ],
    )
    def test_match_first_pattern_text(self, text, patterns, expected):
        """Test first matched pattern text extraction with various inputs."""
        assert match_first_pattern_text(text, patterns) == expected

    def test_invalid_regex_triggers_warning_and_continues(self):
        """Test that invalid regex patterns warn and skip to the next pattern."""
        patterns = {"[unclosed": "skip", "rewe": "groceries"}
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = match_first_pattern_text("REWE MARKT", patterns)
        assert result == "rewe"
        assert len(w) == 1
        assert issubclass(w[0].category, SyntaxWarning)
        assert "Invalid regex pattern" in str(w[0].message)


class TestFindAllColumns:
    """Tests for find_all_columns function."""

    @pytest.mark.parametrize(
        "columns,possibilities,expected",
        [
            (
                ["Date", "Merchant", "Description", "Amount"],
                ["Merchant", "Description"],
                ["Merchant", "Description"],
            ),
            (
                ["Date", "Merchant", "Description"],
                ["merchant", "description"],
                ["Merchant", "Description"],
            ),
            (
                ["Date", "Merchant", "Amount"],
                ["Merchant", "Description"],
                ["Merchant"],
            ),
            (["Date", "Amount"], ["Merchant", "Description"], []),
            (["Date", "Amount"], [], []),
        ],
    )
    def test_find_all_columns_results(self, columns, possibilities, expected):
        """Test finding all matching columns."""
        assert find_all_columns(columns, possibilities) == expected


class TestNormalizeCombinedText:
    """Tests for normalize_combined_text function."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("REWE MARKT\n1234\nBerlin", "rewe markt 1234 berlin"),
            ("REWE\tMARKT\t1234", "rewe markt 1234"),
            ("REWE   MARKT    1234", "rewe markt 1234"),
            ("REWE MARKT", "rewe markt"),
            ("  REWE MARKT  ", "rewe markt"),
            ("  REWE MARKT\n  1234\n  BERLIN  ", "rewe markt 1234 berlin"),
            ("", ""),
            ("  \n\t  ", ""),
        ],
    )
    def test_normalize_text(self, text, expected):
        """Test text normalization with various inputs."""
        assert normalize_combined_text(text) == expected
