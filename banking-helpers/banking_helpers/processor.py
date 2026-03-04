"""CSV processor for banking transactions."""

import io
from typing import Optional

import pandas as pd
from banking_helpers.utils import (
    find_all_columns,
    find_column,
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
        """
        # Read CSV with skip_rows and delimiter if configured
        skip_rows: int = self.bank_config.get("skip_rows", 0)
        delimiter: str = self.bank_config.get("delimiter", ",")

        df: pd.DataFrame = pd.read_csv(
            io.BytesIO(csv_content),
            skiprows=skip_rows,
            delimiter=delimiter,
            encoding="utf-8",
            on_bad_lines="skip",
            encoding_errors="replace",
        )

        # Validate CSV data
        if df.empty:
            raise ValueError("CSV file is empty or contains no valid data rows")
        if len(df.columns) == 0:
            raise ValueError("CSV file contains no columns")

        # Build output DataFrame
        output_data: dict[str, list] = {}

        # Process each required output column
        for col_config in self.output_config.columns:

            col_name: str = col_config.name
            required: bool = col_config.get("required", True)

            # Get mapping configuration
            mapping: Optional[DictConfig] = (
                self.bank_config.column_mappings.get(col_name)
            )

            if not mapping:
                if required:
                    raise ValueError(
                        f"No column mapping for required column: {col_name}"
                    )
                continue

            parser_type: str = mapping.parser

            # Literal: fixed value per row (no source column)
            if parser_type == "literal":
                literal_val: str = str(mapping.get("value") or "")
                output_data[col_name] = [literal_val] * len(df)
                continue

            # Find source column for non-literal parsers
            source_columns: list[str] = mapping.get("source_columns", [])
            source_col: Optional[str] = (
                find_column(df.columns.tolist(), source_columns)
                if source_columns
                else None
            )

            if not source_col:
                if required:
                    raise ValueError(
                        f"Required column '{col_name}' not found. "
                        f"Tried: {', '.join(source_columns)}"
                    )
                continue

            # Parse based on parser type
            if parser_type == "date":
                input_date_format: Optional[str] = self.bank_config.get(
                    "date_format"
                )
                output_data[col_name] = [
                    (
                        format_date(
                            parse_date(str(val), input_date_format),
                            self.date_format,
                        )
                        if pd.notna(val)
                        else ""
                    )
                    for val in df[source_col]
                ]
            elif parser_type == "amount":
                positive_is: str = mapping.get("positive_is", "debit")
                decimal_separator: str = mapping.get("decimal_separator", ".")
                output_data[col_name] = [
                    (
                        parse_amount(str(val), positive_is, decimal_separator)
                        if pd.notna(val)
                        else 0.0
                    )
                    for val in df[source_col]
                ]
            elif parser_type == "string":
                source_columns: list[str] = mapping.get("source_columns", [])

                # Find ALL matching source columns (not just first)
                all_source_cols: list[str] = (
                    find_all_columns(df.columns.tolist(), source_columns)
                    if source_columns
                    else []
                )

                try:
                    if not all_source_cols:
                        # No source columns found, use empty string
                        output_data[col_name] = [""] * len(df)
                    else:
                        # Combine all source columns and normalize
                        output_data[col_name] = [
                            normalize_combined_text(
                                " ".join(
                                    (
                                        str(df[col].iloc[idx])
                                        if pd.notna(df[col].iloc[idx])
                                        else ""
                                    )
                                    for col in all_source_cols
                                )
                            )
                            for idx in range(len(df))
                        ]
                except Exception as e:
                    raise ValueError(
                        f"Error in string parsing for column "
                        f"'{col_name}': {str(e)}"
                    ) from e
            elif parser_type == "pattern_category":
                patterns: dict[str, str] = mapping.get("patterns", {})
                default_category: str = mapping.get("default", "")
                source_columns: list[str] = mapping.get("source_columns", [])

                # Find ALL matching source columns (not just first)
                all_source_cols: list[str] = (
                    find_all_columns(df.columns.tolist(), source_columns)
                    if source_columns
                    else []
                )

                try:
                    if not all_source_cols:
                        # No source columns found, use default
                        output_data[col_name] = [default_category] * len(df)
                    else:
                        # Combine all source columns and match patterns
                        output_data[col_name] = [
                            match_category_pattern(
                                normalize_combined_text(
                                    " ".join(
                                        (
                                            str(df[col].iloc[idx])
                                            if pd.notna(df[col].iloc[idx])
                                            else ""
                                        )
                                        for col in all_source_cols
                                    )
                                ),
                                patterns,
                            )
                            or default_category
                            for idx in range(len(df))
                        ]
                except Exception as e:
                    raise ValueError(
                        f"Error in pattern_category parsing for column "
                        f"'{col_name}': {str(e)}"
                    ) from e
            else:
                raise ValueError(f"Unknown parser type: {parser_type}")

        output_df = pd.DataFrame(output_data)

        if "Date" in output_df.columns:
            output_df = output_df.sort_values("Date", ascending=True)

        return output_df
