# Pattern Configuration Quick Reference

## Your 21 Categories

**Auto-assigned via patterns (5):**
- ✅ groceries - supermarket stores
- ✅ utilities - electricity, gas, water
- ✅ rent - housing payments
- ✅ fun - entertainment/streaming
- ✅ household - default fallback

**Manual categories in Excel dropdowns (16):**
- clothing
- clothing - special
- donation
- insurance
- medical
- pet groceries
- pet medical
- presents
- sports
- takeout
- taxes
- transit
- vacation
- work
- xfer

## Current Patterns (All Banks)

```yaml
patterns:
  "rewe|edeka|aldi|penny|lidl|kaufland|netto": "groceries"
  "strom|gas|wasser|elektrizität": "utilities"
  "miete|nebenkosten|rent": "rent"
  "spotify|netflix|disney|amazon prime video": "fun"
default: "household"
```

## Expanding Patterns

To add more auto-assigned categories, edit any bank config (e.g., `config/banks/dkb.yaml`):

```yaml
patterns:
  # Existing patterns
  "rewe|edeka|aldi|penny|lidl|kaufland|netto": "groceries"
  "strom|gas|wasser|elektrizität": "utilities"
  "miete|nebenkosten|rent": "rent"
  "spotify|netflix|disney|amazon prime video": "fun"
  
  # New patterns (examples)
  "restaurant|lieferando|uber eats|deliveroo": "takeout"
  "zalando|h&m|inditex|about you": "clothing"
  "tierarzt|animal hospital": "pet medical"
  "dm|rossmann|apotheke": "medical"
  "db|mvg|öpnv|bvg": "transit"
  "booking|airbnb|hotel": "vacation"
  
default: "household"
```

## Pattern Syntax Cheat Sheet

| Symbol | Meaning | Example |
|--------|---------|---------|
| `\|` | OR | `bank1\|bank2` |
| `.` | Any char | `a.c` → "abc", "adc" |
| `.*` | Any chars | `amazon.*video` |
| `\d` | Digit | `invoice\d{3}` |
| `^` | Start | `^amazon` (begins with) |
| `$` | End | `bank$` (ends with) |
| `[ ]` | Set | `[aeiou]` (any vowel) |

## Testing

```bash
# Process CSV and see categories
poetry run python -m banking_helpers.cli data/dkb.csv dkb

# Export to Excel with dropdowns
poetry run python -m banking_helpers.cli data/dkb.csv dkb -o output.xlsx -f excel

# List available banks
poetry run python -m banking_helpers.cli --list-banks
```

## Excel Workflow

1. Process CSV: `poetry run python -m banking_helpers.cli data.csv dkb -o clean.xlsx -f excel`
2. Open Excel file
3. For cells marked "household" (auto-assigned or default), use dropdown to manually select correct category
4. Save and re-import for further processing

## Bank Configs

All 3 German banks use identical patterns:
- `config/banks/dkb.yaml` - DKB
- `config/banks/sparkasse.yaml` - Sparkasse
- `config/banks/vrbank.yaml` - VR Bank

Default (example bank, uses comma delimiter):
- `config/banks/bank1.yaml` - Example Bank

## Validation Config

All 21 categories in dropdowns:
- `config/validation.yaml`

## Docs

- Full guide: `CATEGORY_PATTERNS.md`
- This quick ref: `PATTERNS_QUICK_REFERENCE.md`

