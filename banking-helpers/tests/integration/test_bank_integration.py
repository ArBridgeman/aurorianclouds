"""Integration tests for banking-helpers processor with real CSV files."""

import pytest
from banking_helpers.processor import CSVProcessor


class TestBankIntegration:
    """Integration tests for bank CSV format."""

    def test_bank_full_csv_processing(self, bank_config, output_config):
        """
        Test processing a real multi-line bank CSV file.

        This test verifies:
        - Correct number of rows processed
        - Date parsing and formatting (MM/DD/YYYY -> YYYY-MM-DD)
        - Amount parsing with credit sign handling
        - Description combining multiple columns
        - Literal column values applied correctly
        - Sorting by date
        """
        # Configure for bank format (comma-delimited, MM/DD/YYYY dates)
        bank_config.delimiter = ","
        bank_config.date_format = "MM/DD/YYYY"
        bank_config.column_mappings.Amount.positive_is = "credit"

        csv_content = b"""Transaction Date,Amount,Description,Memo
01/15/2026,150.00,Grocery Store,Weekly shopping
01/10/2026,-50.00,Salary Deposit,Monthly salary
02/01/2026,29.99,Netflix Subscription,Monthly streaming
01/20/2026,1200.00,Rent Payment,February rent
01/25/2026,-200.00,ATM Withdrawal,Cash withdrawal"""

        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        result = processor.process(csv_content)

        # Verify row count
        assert len(result) == 5, f"Expected 5 rows, got {len(result)}"

        # Verify columns exist
        expected_columns = {
            "Date",
            "Category",
            "Payment",
            "Payer",
            "Benefiter",
            "Amount",
            "To-update",
            "Description",
        }
        assert set(result.columns) == expected_columns

        # Verify dates are parsed and sorted correctly
        dates = result["Date"].tolist()
        assert dates == [
            "2026-01-10",
            "2026-01-15",
            "2026-01-20",
            "2026-01-25",
            "2026-02-01",
        ]

        # Verify amounts are parsed correctly (credit sign handling: positive stays positive)
        amounts = result["Amount"].tolist()
        assert amounts[0] == -50.00, "Salary should be negative (credit)"
        assert amounts[1] == 150.00, "Grocery should be positive (debit)"
        assert amounts[2] == 1200.00, "Rent should be positive (debit)"
        assert amounts[3] == -200.00, "Withdrawal should be negative (credit)"
        assert amounts[4] == 29.99, "Netflix should be positive (debit)"

        # Verify descriptions are combined and normalized
        descriptions = result["Description"].tolist()
        assert descriptions[0] == "salary deposit monthly salary"
        assert descriptions[1] == "grocery store weekly shopping"
        assert descriptions[2] == "rent payment february rent"
        assert descriptions[3] == "atm withdrawal cash withdrawal"
        assert descriptions[4] == "netflix subscription monthly streaming"

        # Verify literal columns
        assert all(result["Payment"] == "joint")
        assert all(result["Payer"] == "john")
        assert all(result["Benefiter"] == "shared")
        # Category uses pattern matching on Description
        assert (
            result["Category"].iloc[0] == "household"
        )  # Salary Deposit (no match)
        assert (
            result["Category"].iloc[1] == "household"
        )  # Grocery Store (no match)
        assert (
            result["Category"].iloc[2] == "household"
        )  # Netflix (no match, need spotify pattern)
        assert (
            result["Category"].iloc[3] == "household"
        )  # Rent Payment (no match)
        assert all(result["To-update"] == "")

    def test_bank_single_transaction(self, bank_config, output_config):
        """Test processing a single transaction."""
        bank_config.delimiter = ","
        bank_config.date_format = "MM/DD/YYYY"
        bank_config.column_mappings.Amount.positive_is = "credit"

        csv_content = b"Transaction Date,Amount,Description\n03/05/2026,99.99,Test Purchase"

        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        result = processor.process(csv_content)

        assert len(result) == 1
        assert result["Date"].iloc[0] == "2026-03-05"
        assert result["Amount"].iloc[0] == 99.99
        assert result["Description"].iloc[0] == "test purchase"

    def test_bank_with_missing_optional_columns(
        self, bank_config, output_config
    ):
        """Test processing CSV with missing optional memo column."""
        bank_config.delimiter = ","
        bank_config.date_format = "MM/DD/YYYY"
        bank_config.column_mappings.Amount.positive_is = "credit"

        csv_content = (
            b"Transaction Date,Amount,Description\n01/15/2026,50.00,Store A"
        )

        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        result = processor.process(csv_content)

        assert len(result) == 1
        # Description should still work with just one source column
        assert result["Description"].iloc[0] == "store a"

    @pytest.mark.parametrize(
        "csv_content,expected_amount",
        [
            (
                b"Transaction Date,Amount,Description\n01/15/2026,-100.00,Deposit",
                -100.00,
            ),
            (
                b"Transaction Date,Amount,Description\n01/15/2026,0.00,Zero transaction",
                0.0,
            ),
        ],
    )
    def test_amount_handling(
        self, bank_config, output_config, csv_content, expected_amount
    ):
        """Test amount handling edge cases."""
        bank_config.delimiter = ","
        bank_config.date_format = "MM/DD/YYYY"
        bank_config.column_mappings.Amount.positive_is = "credit"

        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        result = processor.process(csv_content)
        assert result["Amount"].iloc[0] == expected_amount

    def test_bank_date_boundary_conditions(self, bank_config, output_config):
        """Test date parsing at year boundaries."""
        bank_config.delimiter = ","
        bank_config.date_format = "MM/DD/YYYY"
        bank_config.column_mappings.Amount.positive_is = "credit"

        csv_content = b"""Transaction Date,Amount,Description
12/31/2025,100.00,Year end
01/01/2026,50.00,New year
02/28/2026,75.00,End of February"""

        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        result = processor.process(csv_content)

        dates = result["Date"].tolist()
        assert "2025-12-31" in dates
        assert "2026-01-01" in dates
        assert "2026-02-28" in dates

    def test_bank_special_characters_in_description(
        self, bank_config, output_config
    ):
        """Test handling of special characters in description."""
        bank_config.delimiter = ","
        bank_config.date_format = "MM/DD/YYYY"
        bank_config.column_mappings.Amount.positive_is = "credit"

        csv_content = b'Transaction Date,Amount,Description\n01/15/2026,50.00,"Store & Co., Inc."'

        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        result = processor.process(csv_content)

        # Should normalize and lowercase special characters
        assert result["Description"].iloc[0] == "store & co., inc."

    def test_bank_whitespace_handling(self, bank_config, output_config):
        """Test that whitespace is properly normalized."""
        bank_config.delimiter = ","
        bank_config.date_format = "MM/DD/YYYY"
        bank_config.column_mappings.Amount.positive_is = "credit"

        csv_content = b"Transaction Date,Amount,Description,Memo\n01/15/2026,50.00,  Store   Name  ,  Extra   Info  "

        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        result = processor.process(csv_content)

        # Multiple spaces should be collapsed to single space
        assert result["Description"].iloc[0] == "store name extra info"

    def test_bank_column_order_preservation(self, bank_config, output_config):
        """Test that output columns are in expected order."""
        bank_config.delimiter = ","
        bank_config.date_format = "MM/DD/YYYY"
        bank_config.column_mappings.Amount.positive_is = "credit"

        csv_content = (
            b"Transaction Date,Amount,Description\n01/15/2026,50.00,Test"
        )

        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        result = processor.process(csv_content)

        # Columns should match output config order
        expected_order = [
            "Date",
            "Category",
            "Payment",
            "Payer",
            "Benefiter",
            "Amount",
            "To-update",
            "Description",
        ]
        assert list(result.columns) == expected_order

    def test_bank_large_dataset(self, bank_config, output_config):
        """Test processing a larger dataset (100 transactions)."""
        bank_config.delimiter = ","
        bank_config.date_format = "MM/DD/YYYY"
        bank_config.column_mappings.Amount.positive_is = "credit"

        # Generate 100 transactions
        lines = ["Transaction Date,Amount,Description"]
        for i in range(100):
            day = (i % 28) + 1
            amount = (i * 10.50) % 1000
            lines.append(f"01/{day:02d}/2026,{amount:.2f},Transaction {i}")

        csv_content = "\n".join(lines).encode("utf-8")

        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        result = processor.process(csv_content)

        assert len(result) == 100
        assert result["Date"].iloc[0] == "2026-01-01"
        assert all(
            col in result.columns for col in ["Date", "Amount", "Description"]
        )

    def test_bank_description_from_multiple_columns(
        self, bank_config, output_config
    ):
        """Test that description combines multiple source columns correctly."""
        bank_config.delimiter = ","
        bank_config.date_format = "MM/DD/YYYY"
        bank_config.column_mappings.Amount.positive_is = "credit"

        csv_content = b"Transaction Date,Amount,Description,Memo,Payee\n01/15/2026,50.00,Store,Extra details,Primary name"

        processor = CSVProcessor(bank_config, output_config, "YYYY-MM-DD")
        result = processor.process(csv_content)

        # Should combine Description, Memo, and Payee columns
        assert (
            result["Description"].iloc[0] == "store extra details primary name"
        )
