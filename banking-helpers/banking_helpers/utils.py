"""Utility functions for CSV processing."""

import re
from datetime import datetime
from typing import Optional

from dateutil import parser as date_parser


def match_category_pattern(text: str, patterns: dict[str, str]) -> str:
    """
    Match text against a dictionary of regex patterns and return the category.

    Patterns are matched in order (Python 3.7+) against the input text in a
    case-insensitive manner. The first matching pattern's category is returned.

    Args:
        text: Text to match against patterns (typically a Description field)
        patterns: Dictionary mapping regex patterns to category names.
                 Example: {"rewe|edeka": "groceries", "amazon|ebay": "shopping"}
                 Patterns support full regex syntax (|, ., *, etc.).
                 Dictionary order is preserved in Python 3.7+.

    Returns:
        Matched category name as string, or empty string if no pattern matches.

    Raises:
        re.error: If a pattern contains invalid regex syntax.

    Example:
        >>> patterns = {
        ...     "rewe|edeka|aldi": "groceries",
        ...     "amazon|ebay": "shopping",
        ...     "spotify|netflix": "entertainment"
        ... }
        >>> match_category_pattern("REWE MARKT GMBH", patterns)
        'groceries'
    """
    if not patterns:
        return ""

    text_lower = text.lower()

    for pattern, category in patterns.items():
        try:
            # Case-insensitive pattern matching
            if re.search(pattern, text_lower, re.IGNORECASE):
                return str(category)
        except re.error as e:
            # Log invalid regex and continue to next pattern
            import warnings

            warnings.warn(
                f"Invalid regex pattern '{pattern}' in category matching: {e}",
                SyntaxWarning,
                stacklevel=2,
            )
            continue

    return ""


def parse_date(date_str: str, input_format: Optional[str] = None) -> datetime:
    """
    Parse a date string to datetime object.

    Args:
        date_str: Date string to parse
        input_format: Optional format (e.g. "MM/DD/YYYY", "DD/MM/YYYY").
            If None, uses dateutil's flexible parser.

    Returns:
        Parsed datetime object

    Raises:
        ValueError: If date cannot be parsed
    """
    if input_format:
        # Convert custom format strings to Python strftime format
        format_map: dict[str, str] = {
            "YYYY-MM-DD": "%Y-%m-%d",
            "MM/DD/YYYY": "%m/%d/%Y",
            "DD/MM/YYYY": "%d/%m/%Y",
            "DD.MM.YYYY": "%d.%m.%Y",
            "DD.MM.YY": "%d.%m.%y",
        }
        python_format: str = format_map.get(input_format, input_format)
        return datetime.strptime(date_str.strip(), python_format)
    return date_parser.parse(date_str.strip())


def format_date(dt: datetime, output_format: str) -> str:
    """
    Format datetime object to string.

    Args:
        dt: Datetime object to format
        output_format: Format string (e.g., "YYYY-MM-DD", "MM/DD/YYYY")

    Returns:
        Formatted date string
    """
    # Convert format strings to Python strftime format
    format_map: dict[str, str] = {
        "YYYY-MM-DD": "%Y-%m-%d",
        "MM/DD/YYYY": "%m/%d/%Y",
        "DD/MM/YYYY": "%d/%m/%Y",
        "DD.MM.YYYY": "%d.%m.%Y",
        "DD.MM.YY": "%d.%m.%y",
    }

    python_format: str = format_map.get(output_format, output_format)
    return dt.strftime(python_format)


def parse_amount(
    amount_str: str, positive_is: str = "debit", decimal_separator: str = "."
) -> float:
    """
    Parse amount string to float.

    Args:
        amount_str: Amount string (may contain currency symbols, commas, etc.)
        positive_is: Whether positive values represent "debit" or "credit"
        decimal_separator: '.' for US format, ',' for German format.

    Returns:
        Parsed amount as float (negative for debits, positive for credits)

    Raises:
        ValueError: If amount cannot be parsed
    """
    # Remove currency symbols and whitespace
    parsed: str = amount_str.strip().replace("$", "").replace("€", "").strip()

    # Handle German number format (comma as decimal, dot as thousands separator)
    if decimal_separator == ",":
        # Replace dot (thousands) with nothing, comma (decimal) with dot
        parsed = parsed.replace(".", "").replace(",", ".")
    else:
        # US format: remove thousands separator (comma)
        parsed = parsed.replace(",", "")

    try:
        amount: float = float(parsed)
    except ValueError as e:
        raise ValueError(f"Could not parse amount: {amount_str}") from e

    # Output: negative = debits, positive = credits.
    # positive_is = what positive values in the CSV mean:
    # - "credit": no conversion (positive stays +, negative stays -).
    # - "debit": flip sign (positive → negative, negative → positive).
    if positive_is == "debit":
        # Flip sign
        return -amount

    # positive_is="credit": standard format, no conversion needed
    return amount


def find_column(
    df_columns: list[str], possible_names: list[str]
) -> Optional[str]:
    """
    Find the first matching column name from a list of possibilities.

    Args:
        df_columns: List of actual column names in DataFrame
        possible_names: List of possible column names to search for

    Returns:
        First matching column name, or None if not found
    """
    for name in possible_names:
        name_lower: str = name.lower().strip()
        for col in df_columns:
            if col.lower().strip() == name_lower:
                return col

    return None


def find_all_columns(
    df_columns: list[str], possible_names: list[str]
) -> list[str]:
    """
    Find all matching column names from a list of possibilities.

    Args:
        df_columns: List of actual column names in DataFrame
        possible_names: List of possible column names to search for

    Returns:
        List of matching column names in order, or empty list if none found
    """
    matching_cols: list[str] = []
    for name in possible_names:
        name_lower: str = name.lower().strip()
        for col in df_columns:
            if col.lower().strip() == name_lower:
                matching_cols.append(col)
                break  # Found this name, move to next possible name
    return matching_cols


def normalize_combined_text(text: str) -> str:
    """
    Normalize combined text by removing extra whitespace and newlines.

    Converts to lowercase, removes line breaks, collapses multiple spaces
    into single spaces, and strips leading/trailing whitespace.

    Args:
        text: Text to normalize

    Returns:
        Normalized text (lowercase, cleaned whitespace)

    Example:
        >>> text = "REWE MARKT\\n  1234\\n  Berlin"
        >>> normalize_combined_text(text)
        'rewe markt 1234 berlin'
    """
    # Convert to lowercase
    text_lower = text.lower()
    # Replace newlines and tabs with spaces
    text_cleaned = text_lower.replace("\n", " ").replace("\t", " ")
    # Collapse multiple spaces into single space
    text_normalized = " ".join(text_cleaned.split())
    return text_normalized
