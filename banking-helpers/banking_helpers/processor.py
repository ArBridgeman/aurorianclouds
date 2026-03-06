"""CSV processor for banking transactions."""

import io

import pandas as pd
import pandera.pandas as pa
from banking_helpers.utils import (
    find_all_columns,
    format_date,
    match_category_pattern,
    normalize_combined_text,
    parse_amount,
    parse_date,
)
from omegaconf import DictConfig


class CSVProcessor:
    """Processes banking CSV files according to configuration."""

    def __init__(
        self,
        bank_config: DictConfig,
        output_config: DictConfig,
        date_format: str,
    ) -> None:
        """
        Initialize processor with configurations.

        Args:
            bank_config: Bank-specific config (column mappings, formats, etc.)
            output_config: Output format configuration (column definitions)
            date_format: Output date format string
        """
        self.bank_config: DictConfig = bank_config
        self.output_config: DictConfig = output_config
        self.schema = self._build_schema()
        self.date_format: str = date_format

    def process(self, csv_content: bytes) -> pd.DataFrame:
        """
        Process CSV content and return cleaned DataFrame.

        Args:
            csv_content: Raw CSV file content as bytes

        Returns:
            Cleaned DataFrame with standardized columns

        Raises:
            ValueError: If required columns are missing or data invalid
            pa.SchemaError: If output validation fails
        """
        df = self._read_csv(csv_content)
        self._validate_csv(df)

        output_data = {}
        for col_config in self.output_config.columns:
            col_name = col_config.name
            required = col_config.get("required", True)

            mapping = self.bank_config.column_mappings.get(col_name)
            if not mapping:
                if required:
                    raise ValueError(
                        f"No column mapping for required column: {col_name}"
                    )
                continue

            parser_type = mapping.parser
            if parser_type == "literal":
                output_data[col_name] = self._parse_literal_column(
                    mapping, len(df)
                )
            else:
                output_data[col_name] = self._parse_data_column(
                    df, mapping, col_name, required
                )

        output_df = pd.DataFrame(output_data)
        if "Date" in output_df.columns:
            output_df = self._sort_by_date(output_df, col="Date")

        # Validate output DataFrame against schema
        self._validate_output(output_df)

        return output_df

    def _build_schema(self) -> pa.DataFrameSchema:
        """
        Build Pandera schema from output_config and bank_config.

        Infers column types from the parser type defined in the bank_config,
        not from column names.

        Returns:
            DataFrameSchema with column definitions and constraints
        """
        columns = {}
        for col_config in self.output_config.columns:
            col_name = col_config.name
            required = col_config.get("required", True)

            # Skip optional columns in validation - they may have placeholder values
            if not required:
                continue

            # Get the parser type from bank_config to infer dtype
            mapping = self.bank_config.column_mappings.get(col_name)
            if not mapping:
                continue

            parser_type = mapping.parser

            # Infer dtype based on parser type
            if parser_type == "date":
                dtype = pa.Column(pa.String)
            elif parser_type == "amount":
                dtype = pa.Column(float)
            else:
                # literal, string, pattern_category, etc. → str
                dtype = pa.Column(pa.String)

            columns[col_name] = dtype

        return pa.DataFrameSchema(
            columns=columns,
            strict=False,  # Allow extra columns
            coerce=True,  # Coerce types to match schema
        )

    def _validate_output(self, df: pd.DataFrame) -> None:
        """
        Validate output DataFrame against schema.

        Args:
            df: DataFrame to validate

        Raises:
            pa.SchemaError: If validation fails
        """
        self.schema.validate(df, lazy=False)

    def _read_csv(self, csv_content: bytes) -> pd.DataFrame:
        """Read CSV content into DataFrame with configured settings."""
        skip_rows = self.bank_config.get("skip_rows", 0)
        delimiter = self.bank_config.get("delimiter", ",")

        try:
            return pd.read_csv(
                io.BytesIO(csv_content),
                skiprows=skip_rows,
                delimiter=delimiter,
                encoding="utf-8",
                on_bad_lines="skip",
                encoding_errors="replace",
            )
        except pd.errors.EmptyDataError:
            raise ValueError("CSV file is empty or contains no valid data rows")

    @staticmethod
    def _validate_csv(df: pd.DataFrame) -> None:
        """Validate that CSV has required structure."""
        if len(df.columns) == 0:
            raise ValueError("CSV file contains no columns")

    @staticmethod
    def _find_source_columns(
        df: pd.DataFrame, mapping: DictConfig
    ) -> list[str]:
        """Find all matching source columns for a mapping."""
        source_columns = mapping.get("source_columns", [])
        return (
            find_all_columns(df.columns.tolist(), source_columns)
            if source_columns
            else []
        )

    @staticmethod
    def _parse_literal_column(mapping: DictConfig, num_rows: int) -> list[str]:
        """Parse literal column (fixed value for all rows)."""
        literal_val = str(mapping.get("value") or "")
        return [literal_val] * num_rows

    def _parse_data_column(
        self,
        df: pd.DataFrame,
        mapping: DictConfig,
        col_name: str,
        required: bool,
    ) -> list:
        """Parse data column using appropriate parser type."""
        source_columns = self._find_source_columns(df, mapping)

        if not source_columns:
            if required:
                tried_cols = mapping.get("source_columns", [])
                raise ValueError(
                    f"Required column '{col_name}' not found. Tried: {', '.join(tried_cols)}"
                )
            return [""] * len(df)

        parser_type = mapping.parser
        try:
            if parser_type == "date":
                return self._parse_date_column(df, mapping, source_columns)
            elif parser_type == "amount":
                return self._parse_amount_column(mapping, source_columns, df)
            elif parser_type == "string":
                return self._parse_string_column(df, source_columns)
            elif parser_type == "pattern_category":
                return self._parse_pattern_category_column(
                    df, mapping, source_columns
                )
            else:
                raise ValueError(f"Unknown parser type: {parser_type}")
        except Exception as e:
            raise ValueError(
                f"Error parsing column '{col_name}': {str(e)}"
            ) from e

    def _parse_date_column(
        self, df: pd.DataFrame, mapping: DictConfig, source_columns: list[str]
    ) -> list[str]:
        """Parse date column using first source column."""
        source_col = source_columns[0]  # Use first matching column
        input_date_format = self.bank_config.get("date_format")

        return [
            (
                format_date(
                    parse_date(str(val), input_date_format), self.date_format
                )
                if pd.notna(val)
                else ""
            )
            for val in df[source_col]
        ]

    @staticmethod
    def _parse_amount_column(
        mapping: DictConfig, source_columns: list[str], df: pd.DataFrame
    ) -> list[float]:
        """Parse amount column using first source column."""
        source_col = source_columns[0]  # Use first matching column
        positive_is = mapping.get("positive_is", "debit")
        decimal_separator = mapping.get("decimal_separator", ".")

        return [
            (
                parse_amount(str(val), positive_is, decimal_separator)
                if pd.notna(val)
                else 0.0
            )
            for val in df[source_col]
        ]

    @staticmethod
    def _parse_string_column(
        df: pd.DataFrame, source_columns: list[str]
    ) -> list[str]:
        """Parse string column combining all source columns."""
        return [
            normalize_combined_text(
                " ".join(
                    (
                        str(df[col].iloc[idx])
                        if pd.notna(df[col].iloc[idx])
                        else ""
                    )
                    for col in source_columns
                )
            )
            for idx in range(len(df))
        ]

    def _parse_pattern_category_column(
        self, df: pd.DataFrame, mapping: DictConfig, source_columns: list[str]
    ) -> list[str]:
        """Parse pattern category column combining all source columns."""
        patterns = mapping.get("patterns", {})
        default_category = mapping.get("default", "")

        return [
            match_category_pattern(
                normalize_combined_text(
                    " ".join(
                        (
                            str(df[col].iloc[idx])
                            if pd.notna(df[col].iloc[idx])
                            else ""
                        )
                        for col in source_columns
                    )
                ),
                patterns,
            )
            or default_category
            for idx in range(len(df))
        ]

    @staticmethod
    def _sort_by_date(df: pd.DataFrame, col: str = "Date") -> pd.DataFrame:
        """Sort DataFrame by Date column if it exists."""
        df = df.sort_values(col, ascending=True)
        return df
