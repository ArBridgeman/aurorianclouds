"""Utility functions for CSV processing."""

from datetime import datetime
from typing import Optional

from dateutil import parser as date_parser


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
    cleaned: str = amount_str.strip().replace("$", "").replace("€", "").strip()

    # Handle German number format (comma as decimal, dot as thousands separator)
    if decimal_separator == ",":
        # Replace dot (thousands) with nothing, comma (decimal) with dot
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        # US format: remove thousands separator (comma)
        cleaned = cleaned.replace(",", "")

    try:
        amount: float = float(cleaned)
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
