"""Unit tests for banking_helpers.processor module."""

import pandas as pd
import pytest
from banking_helpers.processor import CSVProcessor


@pytest.fixture
def processor(bank_config, output_config):
    """Fixture for CSVProcessor instance."""
    return CSVProcessor(bank_config, output_config, "YYYY-MM-DD")


class TestCSVProcessorInit:
    """Tests for CSVProcessor initialization."""

    def test_init_with_valid_configs(self, bank_config, output_config):
        """Test initialization with valid configs."""
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        assert processor.bank_config == bank_config
        assert processor.output_config == output_config
        assert processor.date_format == "YYYY-MM-DD"

    def test_init_stores_date_format(self, bank_config, output_config):
        """Test that date format is stored correctly."""
        processor = CSVProcessor(bank_config, output_config, "DD.MM.YY")
        assert processor.date_format == "DD.MM.YY"


class TestCSVProcessorValidation:
    """Tests for CSV validation in processor."""

    def test_empty_csv_raises_error(self, processor):
        """Test that empty CSV raises ValueError."""
        csv_content = b""
        with pytest.raises(ValueError, match="CSV file is empty"):
            processor.process(csv_content)

    def test_no_columns_csv_raises_error(self, processor):
        """Test that CSV with no columns raises ValueError."""
        csv_content = b"\n\n\n"
        with pytest.raises((ValueError, pd.errors.ParserError)):
            processor.process(csv_content)

    def test_missing_required_column_raises_error(self, processor):
        """Test that missing required source column raises error."""
        csv_content = b"Description\nREWE MARKT"
        with pytest.raises(ValueError, match="Required column"):
            processor.process(csv_content)

    @pytest.mark.parametrize(
        "csv_text,encoding,expected_description",
        [
            (
                "Date;Description;Amount\n01.01.26;Müller Markt;10.00",
                "cp1252",
                "müller markt",
            ),
            (
                "Date;Description;Amount\n01.01.26;Bäckerei Test;10.00",
                "utf-8-sig",
                "bäckerei test",
            ),
        ],
    )
    def test_read_csv_decodes_german_characters_with_fallback(
        self, processor, csv_text, encoding, expected_description
    ):
        """Test encoding fallback preserves German characters in descriptions."""
        csv_content = csv_text.encode(encoding)
        result = processor.process(csv_content)
        assert result["Description"].iloc[0] == expected_description


class TestCSVProcessorLiteralParser:
    """Tests for literal parser."""

    def test_literal_parser_sets_fixed_value(self, processor):
        """Test that literal parser sets fixed value for all rows."""
        csv_content = b"Date;Description\n01.01.26;REWE MARKT\n02.01.26;SPOTIFY"
        result = processor.process(csv_content)
        assert all(result["Payment"] == "joint")
        assert all(result["Payer"] == "john")
        assert all(result["Benefiter"] == "shared")
        assert len(result) == 2


class TestCSVProcessorDateParser:
    """Tests for date parser."""

    def test_date_parser_formats_dates(self, processor):
        """Test that date parser formats dates correctly."""
        csv_content = b"Date;Description\n01.01.26;REWE MARKT\n15.03.26;SPOTIFY"
        result = processor.process(csv_content)
        assert result["Date"].iloc[0] == "2026-01-01"
        assert result["Date"].iloc[1] == "2026-03-15"

    def test_date_parser_with_different_format(
        self, bank_config, output_config
    ):
        """Test date parser with different input format."""
        bank_config.date_format = "MM/DD/YYYY"
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        csv_content = b"Date;Description\n01/15/2026;REWE MARKT"
        result = processor.process(csv_content)
        assert result["Date"].iloc[0] == "2026-01-15"


class TestCSVProcessorAmountParser:
    """Tests for amount parser."""

    @pytest.mark.parametrize(
        "csv_content,expected_amount",
        [
            (b"Date;Description;Amount\n01.01.26;REWE MARKT;100.50", -100.50),
            (
                "Date;Description;Amount\n01.01.26;TEST;€100.50".encode(
                    "utf-8"
                ),
                -100.50,
            ),
        ],
    )
    def test_amount_parser_formats(
        self, processor, csv_content, expected_amount
    ):
        """Test amount parsing with various formats."""
        result = processor.process(csv_content)
        assert result["Amount"].iloc[0] == expected_amount

    def test_amount_parser_handles_german_format(
        self, bank_config, output_config
    ):
        """Test amount parser with German decimal format."""
        bank_config.column_mappings.Amount.decimal_separator = ","
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        csv_content = b"Date;Description;Amount\n01.01.26;TEST;1.234,56"
        result = processor.process(csv_content)
        assert result["Amount"].iloc[0] == -1234.56


class TestCSVProcessorStringParser:
    """Tests for string parser."""

    def test_string_parser_single_column(self, processor):
        """Test string parser with single column."""
        csv_content = b"Date;Description\n01.01.26;REWE MARKT"
        result = processor.process(csv_content)
        assert result["Description"].iloc[0] == "rewe markt"

    def test_string_parser_normalizes_text(self, processor):
        """Test that string parser normalizes text."""
        csv_content = b"Date;Description\n01.01.26;REWE  MARKT  1234"
        result = processor.process(csv_content)
        assert result["Description"].iloc[0] == "rewe markt 1234"

    @pytest.mark.parametrize(
        "csv_content,expected_description",
        [
            (
                b"Date;Description\n01.01.26;REWE MARKT ORDER 123",
                "rewe",
            ),
            (
                b"Date;Description\n01.01.26;UNKNOWN SHOP 123",
                "unknown shop 123",
            ),
        ],
    )
    def test_string_parser_can_shorten_to_matched_pattern_text(
        self,
        bank_config,
        output_config,
        csv_content,
        expected_description,
    ):
        """Test optional description shortening using category pattern config."""
        bank_config.column_mappings.Description.use_category_pattern_match_for_output = (
            True
        )
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        result = processor.process(csv_content)
        assert result["Description"].iloc[0] == expected_description


class TestCSVProcessorPatternCategoryParser:
    """Tests for pattern_category parser."""

    @pytest.mark.parametrize(
        "csv_content,expected_category",
        [
            (b"Date;Description\n01.01.26;REWE MARKT", "groceries"),
            (b"Date;Description\n01.01.26;UNKNOWN STORE", "household"),
            (b"Date;Description\n01.01.26;SPOTIFY MUSIC", "fun"),
        ],
    )
    def test_pattern_category_matching(
        self, processor, csv_content, expected_category
    ):
        """Test pattern category matching with various inputs."""
        result = processor.process(csv_content)
        assert result["Category"].iloc[0] == expected_category


class TestCSVProcessorMultiColumnParsers:
    """Tests for parsers using multiple columns."""

    def test_string_parser_with_multiple_columns(
        self, bank_config, output_config
    ):
        """Test string parser combining multiple columns."""
        bank_config.column_mappings.Description.source_columns = [
            "Merchant",
            "Purpose",
        ]
        # Make Category optional for this test since we're not testing it
        for col in output_config.columns:
            if col.name == "Category":
                col.required = False
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        csv_content = b"Date;Merchant;Purpose\n01.01.26;REWE MARKT;Groceries"
        result = processor.process(csv_content)
        assert result["Description"].iloc[0] == "rewe markt groceries"

    def test_pattern_category_with_multiple_columns(
        self, bank_config, output_config
    ):
        """Test pattern matching with multiple source columns."""
        bank_config.column_mappings.Category.source_columns = [
            "Merchant",
            "Purpose",
        ]
        # Make Description optional for this test since we're not testing it
        for col in output_config.columns:
            if col.name == "Description":
                col.required = False
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        csv_content = b"Date;Merchant;Purpose\n01.01.26;REWE;Purchase"
        result = processor.process(csv_content)
        assert result["Category"].iloc[0] == "groceries"


class TestCSVProcessorSorting:
    """Tests for date-based sorting."""

    def test_output_sorted_by_date(self, processor):
        """Test that output is sorted by Date column."""
        csv_content = (
            b"Date;Description\n"
            b"15.01.26;SPOTIFY\n"
            b"01.01.26;REWE MARKT\n"
            b"10.01.26;UNKNOWN"
        )
        result = processor.process(csv_content)
        dates = result["Date"].tolist()
        assert dates == ["2026-01-01", "2026-01-10", "2026-01-15"]

    def test_sorting_stable(self, processor):
        """Test that sorting is stable (preserves order for equal dates)."""
        csv_content = (
            b"Date;Description\n"
            b"01.01.26;FIRST\n"
            b"01.01.26;SECOND\n"
            b"01.01.26;THIRD"
        )
        result = processor.process(csv_content)
        # All dates equal, order should be preserved from input
        assert result["Description"].iloc[0] == "first"
        assert result["Description"].iloc[1] == "second"
        assert result["Description"].iloc[2] == "third"


class TestCSVProcessorIntegration:
    """Integration tests for full processing flow."""

    def test_full_processing_flow(self, processor):
        """Test complete CSV processing flow."""
        csv_content = (
            b"Date;Description;Amount\n"
            b"01.01.26;REWE MARKT;50.00\n"
            b"02.01.26;SPOTIFY;10.00\n"
            b"03.01.26;UNKNOWN;20.00"
        )
        result = processor.process(csv_content)

        # Verify structure
        assert len(result) == 3
        assert list(result.columns) == [
            "Date",
            "Category",
            "Payment",
            "Payer",
            "Benefiter",
            "Amount",
            "To-update",
            "Description",
        ]

        # Verify data
        assert result["Date"].iloc[0] == "2026-01-01"
        assert result["Category"].iloc[0] == "groceries"
        assert result["Amount"].iloc[0] == -50.00
        assert result["Payment"].iloc[0] == "joint"

    def test_processing_with_skip_rows(self, bank_config, output_config):
        """Test processing CSV with header rows to skip."""
        bank_config.skip_rows = 1
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        csv_content = (
            b"HEADER ROW TO SKIP\n"
            b"Date;Description;Amount\n"
            b"01.01.26;REWE MARKT;50.00"
        )
        result = processor.process(csv_content)
        assert len(result) == 1
        assert result["Category"].iloc[0] == "groceries"

    def test_processing_with_different_delimiter(
        self, bank_config, output_config
    ):
        """Test processing CSV with different delimiter."""
        bank_config.delimiter = ","
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        csv_content = b"Date,Description,Amount\n01.01.26,REWE MARKT,50.00"
        result = processor.process(csv_content)
        assert len(result) == 1
        assert result["Category"].iloc[0] == "groceries"
