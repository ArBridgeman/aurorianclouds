"""CLI for running the CSV processor without the Streamlit UI."""

import argparse
import sys
from pathlib import Path
from typing import Any

from banking_helpers.excel_export import write_excel_with_validation
from banking_helpers.processor import CSVProcessor
from omegaconf import DictConfig, OmegaConf


def get_config_dir() -> Path:
    """Return the path to the config directory."""
    return Path(__file__).resolve().parent / "config"


def list_banks(config_dir: Path) -> dict[str, str]:
    """Return mapping of bank display names to config keys (e.g. BANK1 -> bank1)."""
    banks_dir: Path = config_dir / "banks"
    banks: dict[str, str] = {}
    if banks_dir.exists():
        for f in banks_dir.glob("*.yaml"):
            cfg: DictConfig = OmegaConf.load(f)
            name: str = cfg.get("bank_name", f.stem)
            banks[name] = f.stem
    return banks


def run(
    csv_path: Path,
    bank_key: str,
    output_path: Path | None = None,
    output_format: str = "csv",
    print_preview: bool = True,
) -> None:
    """
    Process a CSV file with the given bank config and optionally write output.

    Args:
        csv_path: Path to the input CSV file.
        bank_key: Bank config key (e.g. bank1).
        output_path: If set, write output here; for Excel format required.
        output_format: "csv" or "excel".
        print_preview: If True, print a short preview of the result to stderr.
    """
    config_dir: Path = get_config_dir()
    main_cfg: DictConfig = OmegaConf.load(config_dir / "config.yaml")
    output_cfg: DictConfig = OmegaConf.load(config_dir / "output_format.yaml")
    bank_cfg_path: Path = config_dir / "banks" / f"{bank_key}.yaml"

    if not bank_cfg_path.exists():
        available = list(list_banks(config_dir).values())
        print(
            f"Unknown bank: {bank_key}. Available: {available}",
            file=sys.stderr,
        )
        sys.exit(1)

    bank_cfg: DictConfig = OmegaConf.load(bank_cfg_path)
    processor: CSVProcessor = CSVProcessor(
        bank_config=bank_cfg,
        output_config=output_cfg,
        date_format=main_cfg.date_format,
    )

    csv_bytes: bytes = csv_path.read_bytes()

    df = processor.process(csv_bytes)

    if print_preview:
        print(f"Processed {len(df)} rows.", file=sys.stderr)
        print(df.head(10).to_string(), file=sys.stderr)
        print("---", file=sys.stderr)

    if output_format == "excel":
        if output_path is None:
            output_path = Path("prepared.xlsx")
        validation_path: Path = config_dir / "validation.yaml"
        validation_config: dict[str, list[Any]] = {}
        if validation_path.exists():
            validation_config = (
                OmegaConf.to_container(
                    OmegaConf.load(validation_path), resolve=True
                )
                or {}
            )
        write_excel_with_validation(df, output_path, validation_config)
        print(
            f"Wrote {len(df)} rows to {output_path} (Excel with dropdowns)",
            file=sys.stderr,
        )
        return

    csv_out: str = df.to_csv(index=False)
    if output_path is not None:
        output_path.write_text(csv_out, encoding="utf-8")
        print(f"Wrote {len(df)} rows to {output_path}", file=sys.stderr)
    else:
        print(csv_out, end="")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process banking CSV files without the Streamlit UI.",
    )
    parser.add_argument(
        "csv_path",
        type=Path,
        nargs="?",
        default=None,
        help="Path to the input CSV file (not needed with --list-banks)",
    )
    parser.add_argument(
        "bank",
        type=str,
        nargs="?",
        default=None,
        help=("Bank config key (e.g. bank1). " "Use --list-banks to see all."),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write output to this file (default: print CSV to stdout)",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["csv", "excel"],
        default="csv",
        help="Output: csv or excel (excel has dropdowns; use -o for file).",
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Do not print a preview to stderr",
    )
    parser.add_argument(
        "--list-banks",
        action="store_true",
        help="List available bank config keys and exit",
    )

    args = parser.parse_args()
    config_dir: Path = get_config_dir()

    if args.list_banks:
        banks = list_banks(config_dir)
        for name, key in sorted(banks.items(), key=lambda x: x[0].lower()):
            print(f"  {key}: {name}")
        return

    if args.csv_path is None or args.bank is None:
        parser.error(
            "csv_path and bank are required (or use --list-banks to list banks)"
        )

    if not args.csv_path.exists():
        print(f"File not found: {args.csv_path}", file=sys.stderr)
        sys.exit(1)

    if args.format == "excel" and args.output is None:
        args.output = Path("prepared.xlsx")

    try:
        run(
            csv_path=args.csv_path,
            bank_key=args.bank,
            output_path=args.output,
            output_format=args.format,
            print_preview=not args.no_preview,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
