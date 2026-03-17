"""Pytest configuration and shared fixtures."""

import pytest
from omegaconf import OmegaConf


@pytest.fixture(scope="session")
def test_data_dir():
    """Fixture for test data directory path."""
    from pathlib import Path

    return Path(__file__).parent / "data"


@pytest.fixture
def bank_config():
    """Fixture for bank configuration - supports flexible column names."""
    return OmegaConf.create(
        {
            "bank_name": "Test Bank",
            "date_format": "DD.MM.YY",
            "delimiter": ";",
            "skip_rows": 0,
            "column_mappings": {
                "Date": {
                    "source_columns": ["Date", "Transaction Date"],
                    "parser": "date",
                },
                "Category": {
                    "source_columns": ["Description"],
                    "parser": "pattern_category",
                    "patterns": {
                        "rewe|edeka": "groceries",
                        "spotify": "fun",
                    },
                    "default": "household",
                },
                "Payment": {
                    "parser": "literal",
                    "value": "joint",
                },
                "Payer": {
                    "parser": "literal",
                    "value": "john",
                },
                "Benefiter": {
                    "parser": "literal",
                    "value": "shared",
                },
                "Amount": {
                    "source_columns": ["Amount"],
                    "parser": "amount",
                    "positive_is": "debit",
                    "decimal_separator": ".",
                },
                "To-update": {
                    "parser": "literal",
                    "value": "",
                },
                "Description": {
                    "source_columns": ["Description", "Memo", "Payee"],
                    "parser": "string",
                },
            },
        }
    )


@pytest.fixture
def output_config():
    """Fixture for output format configuration."""
    return OmegaConf.create(
        {
            "columns": [
                {"name": "Date", "required": True},
                {"name": "Category", "required": True},
                {"name": "Payment", "required": True},
                {"name": "Payer", "required": True},
                {"name": "Benefiter", "required": True},
                {"name": "Amount", "required": False},
                {"name": "To-update", "required": False},
                {"name": "Description", "required": True},
            ],
        }
    )
