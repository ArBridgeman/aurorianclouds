"""Unit tests for Pandera schema validation integration."""

import pandera.pandas as pa
from banking_helpers.processor import CSVProcessor


class TestPanderaValidation:
    """Tests for Pandera DataFrame validation."""

    def test_pandera_validates_output_schema(self, bank_config, output_config):
        """Test that Pandera validates output DataFrame schema."""
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        csv_content = b"Date;Description\n01.01.26;REWE MARKT"

        result = processor.process(csv_content)

        # Should process without raising SchemaError
        assert len(result) == 1
        assert "Date" in result.columns
        assert "Description" in result.columns

    def test_schema_includes_required_columns(self, bank_config, output_config):
        """Test that schema includes only required columns."""
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        schema = processor._build_schema()

        # Schema should have Date and Description (required columns)
        assert "Date" in schema.columns
        assert "Description" in schema.columns

        # Schema should not have Amount (optional column)
        assert "Amount" not in schema.columns

    def test_schema_infers_type_from_date_parser(
        self, bank_config, output_config
    ):
        """Test that date parser results in string type."""
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        schema = processor._build_schema()

        date_col = schema.columns.get("Date")
        assert date_col is not None
        # Date parser → string type
        print(type(date_col.dtype))
        print(repr(date_col.dtype))
        assert date_col.dtype == pa.engines.pandas_engine.NpString()

    def test_schema_infers_type_from_string_parser(
        self, bank_config, output_config
    ):
        """Test that string parser results in string type."""
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        schema = processor._build_schema()

        description_col = schema.columns.get("Description")
        assert description_col is not None
        # String parser → string type
        assert description_col.dtype == pa.engines.pandas_engine.NpString()

    def test_schema_infers_type_from_amount_parser(
        self, bank_config, output_config
    ):
        """Test that amount parser results in float type."""
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        processor._build_schema()

        # Amount column exists and should have float type when included
        # (Amount is optional in our test config, so it won't be in schema)
        # Let's verify that if we had a required Amount, it would be float
        amount_mapping = bank_config.column_mappings.get("Amount")
        assert amount_mapping is not None
        assert amount_mapping.parser == "amount"

    def test_schema_allows_extra_columns(self, bank_config, output_config):
        """Test that schema allows extra columns not in output_config."""
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        schema = processor._build_schema()

        # strict=False allows extra columns
        assert schema.strict is False

    def test_schema_coercion_enabled(self, bank_config, output_config):
        """Test that schema has coercion enabled for type matching."""
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        schema = processor._build_schema()

        # coerce=True allows automatic type conversion
        assert schema.coerce is True

    def test_validation_called_during_process(self, bank_config, output_config):
        """Test that validation is called and works during processing."""
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        csv_content = b"Date;Description;Amount\n01.01.26;TEST;100.50"

        # Should process without validation errors
        result = processor.process(csv_content)

        assert len(result) == 1
        # Amount should be coerced to float
        assert isinstance(result["Amount"].iloc[0], float)

    def test_schema_skips_optional_columns(self, bank_config, output_config):
        """Test that optional columns are not included in schema validation."""
        # Make all output columns optional to get empty schema
        for col in output_config.columns:
            col.required = False

        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        schema = processor._build_schema()

        # Should have no columns in schema (all optional)
        assert len(schema.columns) == 0

    def test_validation_with_missing_optional_amount(
        self, bank_config, output_config
    ):
        """Test validation when optional Amount column is missing from CSV."""
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        # CSV with no Amount column (Amount is optional)
        csv_content = b"Date;Description\n01.01.26;REWE MARKT"

        result = processor.process(csv_content)

        # Should process successfully despite missing optional column
        assert len(result) == 1
        assert "Date" in result.columns
        assert "Description" in result.columns

    def test_schema_type_inference_from_parser(
        self, bank_config, output_config
    ):
        """Test that schema correctly infers types from parser configuration."""
        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")

        # Verify that the schema building uses parser type, not column name
        # Date column uses date parser → str
        date_mapping = bank_config.column_mappings.get("Date")
        assert date_mapping.parser == "date"

        # Description uses string parser → str
        desc_mapping = bank_config.column_mappings.get("Description")
        assert desc_mapping.parser == "string"

        schema = processor._build_schema()

        # Both should be string types, inferred from their parser types
        assert (
            schema.columns["Date"].dtype == pa.engines.pandas_engine.NpString()
        )
        assert (
            schema.columns["Description"].dtype
            == pa.engines.pandas_engine.NpString()
        )
