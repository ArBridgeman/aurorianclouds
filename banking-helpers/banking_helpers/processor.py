"""CSV processor for banking transactions."""

import io
import re
import warnings
from typing import Optional

import pandas as pd
import pandera.pandas as pa
from banking_helpers.utils import (
    find_all_columns,
    format_date,
    match_category_pattern,
    match_first_pattern_text,
    normalize_combined_text,
    parse_amount,
    parse_date,
)
from omegaconf import DictConfig, OmegaConf


class CSVProcessor:
    """Processes banking CSV files according to configuration."""

    def __init__(
        self,
        bank_config: DictConfig,
        output_config: DictConfig,
        date_format: str,
        rules_config: Optional[DictConfig] = None,
    ) -> None:
        """
        Initialize processor with configurations.

        Args:
            bank_config: Bank-specific config (column mappings, formats, etc.)
            output_config: Output format configuration (column definitions)
            date_format: Output date format string
            rules_config: Optional shared rules config (rules.yaml). When provided,
                rules are applied as a post-processing step after all columns are
                parsed. Bank-level ``extra_rules`` (if any) take priority.
        """
        self.bank_config: DictConfig = bank_config
        self.output_config: DictConfig = output_config
        self.rules_config: Optional[DictConfig] = rules_config
        self.date_format: str = date_format
        self.schema = self._build_schema()
        # Pre-compile rules once; invalid regexes are warned and skipped here.
        self._compiled_rules: list[tuple[re.Pattern, dict]] = (
            self._build_compiled_rules()
        )

    def process(self, csv_content: bytes) -> pd.DataFrame:
        """
        Process CSV content and return prepared DataFrame.

        Args:
            csv_content: Raw CSV file content as bytes

        Returns:
            Prepared DataFrame with standardized columns

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

        # Reset index so label == positional index (required for _apply_rules)
        output_df = output_df.reset_index(drop=True)

        # Apply shared + bank-level pattern rules as a post-processing step
        output_df = self._apply_rules(output_df)

        # Apply bank-level value remappings (e.g. joint → to be split)
        output_df = self._apply_remap_values(output_df)

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
        encodings_to_try = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]

        try:
            last_decode_error: UnicodeDecodeError | None = None
            for encoding in encodings_to_try:
                try:
                    return pd.read_csv(
                        io.BytesIO(csv_content),
                        skiprows=skip_rows,
                        delimiter=delimiter,
                        encoding=encoding,
                        on_bad_lines="skip",
                    )
                except UnicodeDecodeError as e:
                    last_decode_error = e
                    continue

            tried = ", ".join(encodings_to_try)
            raise ValueError(
                f"Could not decode CSV content with encodings: {tried}"
            ) from last_decode_error
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
                return self._parse_amount_column(df, mapping, source_columns)
            elif parser_type == "string":
                return self._parse_string_column(df, mapping, source_columns)
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
        df: pd.DataFrame, mapping: DictConfig, source_columns: list[str]
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
    def _build_normalized_row_texts(
        df: pd.DataFrame, source_columns: list[str]
    ) -> list[str]:
        """Combine and normalize all source text columns row-wise (vectorized)."""
        combined: pd.Series = (
            df[source_columns].fillna("").astype(str).agg(" ".join, axis=1)
        )
        return (
            combined.str.lower()
            .str.replace(r"[\n\t]", " ", regex=True)
            .str.split()
            .str.join(" ")
            .tolist()
        )

    def _parse_string_column(
        self, df: pd.DataFrame, mapping: DictConfig, source_columns: list[str]
    ) -> list[str]:
        """Parse string column, optionally shortening to matched pattern text."""
        combined_texts = self._build_normalized_row_texts(df, source_columns)

        shorten_enabled = bool(
            mapping.get("use_category_pattern_match_for_output", False)
        )
        if not shorten_enabled:
            return combined_texts

        pattern_source_column = mapping.get("pattern_source_column", "Category")
        category_mapping = self.bank_config.column_mappings.get(
            pattern_source_column
        )
        patterns = (
            category_mapping.get("patterns", {}) if category_mapping else {}
        )

        return [
            match_first_pattern_text(text, patterns) or text
            for text in combined_texts
        ]

    def _parse_pattern_category_column(
        self, df: pd.DataFrame, mapping: DictConfig, source_columns: list[str]
    ) -> list[str]:
        """Parse pattern category column combining all source columns."""
        patterns = mapping.get("patterns", {})
        default_category = mapping.get("default", "")
        combined_texts = self._build_normalized_row_texts(df, source_columns)

        return [
            match_category_pattern(
                combined_text,
                patterns,
            )
            or default_category
            for combined_text in combined_texts
        ]

    def _build_compiled_rules(self) -> list[tuple[re.Pattern, dict]]:
        """
        Pre-compile regex patterns from bank extra_rules + global rules.

        Extra rules (bank config) are prepended and evaluated first (higher
        priority). Invalid regex patterns emit a SyntaxWarning and are skipped.
        Called once at construction time so errors surface early.

        Returns:
            List of (compiled_pattern, rule_dict) in evaluation order.
        """
        raw_extra = self.bank_config.get("extra_rules")
        extra_rules: list = (
            list(OmegaConf.to_container(raw_extra, resolve=True))
            if OmegaConf.is_config(raw_extra)
            else list(raw_extra) if raw_extra else []
        )
        raw_global = (
            self.rules_config.get("rules") if self.rules_config else None
        )
        global_rules: list = (
            list(OmegaConf.to_container(raw_global, resolve=True))
            if OmegaConf.is_config(raw_global)
            else list(raw_global) if raw_global else []
        )

        compiled: list[tuple[re.Pattern, dict]] = []
        for rule in extra_rules + global_rules:
            regex_str: str = rule.get("regex", "")
            if not regex_str:
                continue
            try:
                # Cell text is already lowercased before matching
                compiled.append((re.compile(regex_str), rule))
            except re.error as exc:
                warnings.warn(
                    f"Invalid regex in rule '{rule.get('name', '')}': {exc}",
                    SyntaxWarning,
                    stacklevel=2,
                )
        return compiled

    def _apply_rules(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply pre-compiled pattern rules as a post-processing step.

        Bank-level extra_rules (higher priority) are prepended to global rules.
        First matching rule per row wins; remaining rules for that row are skipped.

        When ``shorten_description_on_rule_match: true`` is set in the bank
        config, Description is also replaced with the matched text fragment.

        Args:
            df: Output DataFrame (already sorted, index reset).

        Returns:
            DataFrame with rule-derived column values applied in-place.
        """
        if not self._compiled_rules:
            return df

        shorten_description: bool = bool(
            self.bank_config.get("shorten_description_on_rule_match", False)
        )

        for idx in range(len(df)):
            for pattern, rule in self._compiled_rules:
                match_col: str = rule.get("match_on", "Description")
                if match_col not in df.columns:
                    continue

                cell_value = df.at[idx, match_col]
                if not isinstance(cell_value, str):
                    continue

                match = pattern.search(cell_value.lower())
                if match:
                    for col, value in (rules := rule.get("set") or {}).items():
                        if col in df.columns:
                            df.at[idx, col] = value
                    # rules take precedence over generic shortening
                    if (
                        shorten_description
                        and ("Description" in df.columns)
                        and ("Description" not in rules.keys())
                    ):
                        df.at[idx, "Description"] = normalize_combined_text(
                            match.group(0)
                        )
                    break  # First match wins; skip remaining rules for this row

        return df

    def _apply_remap_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply bank-level value remappings as a final post-processing step.

        Reads ``remap_values`` from the bank config — a mapping of
        ``{column: {old_value: new_value}}``.  Every cell in *column* whose
        value equals *old_value* (exact, case-sensitive) is replaced with
        *new_value*.  The remapping is applied after all rules, so it catches
        values set both by literals and by rule ``set`` directives.

        Example bank config entry::

            remap_values:
              Payment:
                joint: "to be split"

        Args:
            df: Output DataFrame after rules have been applied.

        Returns:
            DataFrame with remapped values applied in-place.
        """
        raw = self.bank_config.get("remap_values")
        if not raw:
            return df

        remap: dict = (
            OmegaConf.to_container(raw, resolve=True)
            if OmegaConf.is_config(raw)
            else dict(raw)
        )

        for col, value_map in remap.items():
            if col not in df.columns:
                continue
            for old_value, new_value in value_map.items():
                df[col] = df[col].replace(old_value, new_value)

        return df

    @staticmethod
    def _sort_by_date(df: pd.DataFrame, col: str = "Date") -> pd.DataFrame:
        """Sort DataFrame by Date column, using a stable sort to preserve input order for equal dates."""
        return df.sort_values(col, ascending=True, kind="stable")
