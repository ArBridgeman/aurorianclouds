# Banking CSV Cleaner

A simple Streamlit application for cleaning and standardizing banking CSV files.

## Features

- **Multiple Bank Support**: Configure different bank CSV formats via YAML files
- **Flexible Configuration**: All input/output formats configurable via Hydra
- **Simple UI**: Upload CSV, select bank format, download cleaned version
- **Handles Messy CSVs**: Skip header rows, flexible column mapping

## Setup

### Local Development

1. Install dependencies:
```bash
poetry install
```

2. Run the application:
```bash
poetry run streamlit run banking_helpers/app.py
```

### Command-line (no UI)

Process a CSV without the Streamlit interface:

```bash
# List available bank configs
poetry run python -m banking_helpers.cli --list-banks

# Process a file (prints cleaned CSV to stdout)
poetry run python -m banking_helpers.cli data/dkb.csv dkb

# Write output to a file
poetry run python -m banking_helpers.cli data/dkb.csv dkb -o cleaned.csv

# Suppress preview (only CSV on stdout)
poetry run python -m banking_helpers.cli data/dkb.csv dkb --no-preview

# Export to Excel with dropdowns (Payer, Payment, Benefiter, etc.)
poetry run python -m banking_helpers.cli data/dkb.csv dkb -f excel \
  -o cleaned.xlsx
```

Use the bank config key (e.g. `dkb`, `sparkasse`, `vrbank`, `bank1`) as the
second argument.

### Docker Deployment

1. Build and run with Docker Compose:
```bash
docker-compose up -d
```

2. Access the application at `http://localhost:8501`

3. To rebuild after code changes:
```bash
docker-compose up -d --build
```

4. To view logs:
```bash
docker-compose logs -f
```

5. To stop:
```bash
docker-compose down
```

**Note**: The config directory is mounted read-only, so you can update bank
configs without rebuilding. Restart the container after config changes:
```bash
docker-compose restart
```

## Configuration

### Adding a New Bank Format

1. Create a new YAML in `banking_helpers/config/banks/` (e.g. `bank2.yaml`)
2. Define the bank format:
```yaml
bank_name: "Your Bank Name"
date_format: "MM/DD/YYYY"  # Input date format
skip_rows: 0  # Rows to skip at the beginning

column_mappings:
  date:
    source_columns: ["Date", "Transaction Date"]
    parser: "date"
  account:
    source_columns: ["Account", "Account Number"]
    parser: "string"
  amount:
    source_columns: ["Amount"]
    parser: "amount"
    positive_is: "debit"  # or "credit"
  description:
    source_columns: ["Description", "Memo"]
    parser: "string"
```

3. The bank will automatically appear in the dropdown menu

### Customizing Output Format

Edit `banking_helpers/config/output_format.yaml` to change output columns.

### Customizing Date Format

Edit `banking_helpers/config/config.yaml` to change the default output date
format.

### Excel dropdowns (validation)

When you download **Excel** (button "Download Excel (with dropdowns)" or CLI
`-f excel`), the `.xlsx` has dropdowns on Payer, Payment, and Benefiter.
Allowed values are in `banking_helpers/config/validation.yaml`. Edit that file
to change options. Opening the `.xlsx` in Google Sheets or Excel keeps the
dropdowns.

## Example CSV

See `example_transactions.csv` for a sample input matching the default
`bank1` configuration.

## Usage

1. Start the Streamlit app
2. Upload your banking CSV file
3. Select the appropriate bank format from the dropdown
4. Click "Process CSV"
5. Review the preview and download the cleaned CSV
