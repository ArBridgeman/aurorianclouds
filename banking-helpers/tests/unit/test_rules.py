"""Unit tests for the _apply_rules post-processing step in CSVProcessor."""

import warnings

import pytest
from banking_helpers.processor import CSVProcessor
from omegaconf import OmegaConf


@pytest.fixture
def processor(rules_bank_config, output_config, rules_config):
    """CSVProcessor with rules_config wired in."""
    return CSVProcessor(
        rules_bank_config,
        output_config,
        "YYYY-MM-DD",
        rules_config=rules_config,
    )


class TestApplyRulesBasic:
    """Core rule-matching behaviour."""

    @pytest.mark.parametrize(
        "description,expected_category",
        [
            ("REWE MARKT GMBH", "groceries"),
            ("EDEKA CENTER BERLIN", "groceries"),
            ("SPOTIFY PREMIUM", "fun"),
            ("NETFLIX MONTHLY", "fun"),
            ("MIETE JANUAR", "rent"),
            ("UNKNOWN STORE", "household"),  # no match → literal default
        ],
    )
    def test_rule_sets_category(
        self, processor, description, expected_category
    ):
        """Global rules correctly assign Category for known and unknown entries."""
        csv_content = f"Date;Description\n01.01.26;{description}".encode()
        result = processor.process(csv_content)
        assert result["Category"].iloc[0] == expected_category

    def test_first_rule_wins(self, rules_bank_config, output_config):
        """When multiple rules match, only the first one is applied."""
        rules = OmegaConf.create(
            {
                "rules": [
                    {
                        "name": "first",
                        "regex": "rewe",
                        "match_on": "Description",
                        "set": {"Category": "groceries"},
                    },
                    {
                        "name": "second",
                        "regex": "rewe|edeka",
                        "match_on": "Description",
                        "set": {"Category": "other"},
                    },
                ]
            }
        )
        processor = CSVProcessor(
            rules_bank_config, output_config, "YYYY-MM-DD", rules_config=rules
        )
        result = processor.process(b"Date;Description\n01.01.26;REWE MARKT")
        assert result["Category"].iloc[0] == "groceries"

    def test_rule_sets_multiple_columns(self, processor):
        """A single rule can overwrite more than one output column at once."""
        result = processor.process(b"Date;Description\n01.01.26;MIETE JANUAR")
        assert result["Category"].iloc[0] == "rent"
        assert result["Payment"].iloc[0] == "direct"

    def test_multiple_rows_matched_independently(self, processor):
        """Each row is evaluated against rules independently."""
        csv_content = (
            b"Date;Description\n"
            b"01.01.26;REWE MARKT\n"
            b"02.01.26;SPOTIFY PREMIUM\n"
            b"03.01.26;UNKNOWN STORE"
        )
        result = processor.process(csv_content)
        assert result["Category"].tolist() == ["groceries", "fun", "household"]

    def test_no_rules_config_keeps_defaults(
        self, rules_bank_config, output_config
    ):
        """Without a rules_config, Category stays at the literal default."""
        processor = CSVProcessor(
            rules_bank_config, output_config, "YYYY-MM-DD", rules_config=None
        )
        result = processor.process(b"Date;Description\n01.01.26;REWE MARKT")
        assert result["Category"].iloc[0] == "household"


class TestApplyRulesPriority:
    """Priority: extra_rules (bank-level) beats global rules."""

    def test_extra_rules_override_global_rules(
        self, rules_bank_config, output_config, rules_config
    ):
        """Bank extra_rules map 'rewe' → takeout, overriding the global groceries rule."""
        rules_bank_config.extra_rules = [
            {
                "name": "bank_override",
                "regex": "rewe",
                "match_on": "Description",
                "set": {"Category": "takeout"},
            }
        ]
        processor = CSVProcessor(
            rules_bank_config,
            output_config,
            "YYYY-MM-DD",
            rules_config=rules_config,
        )
        result = processor.process(b"Date;Description\n01.01.26;REWE MARKT")
        assert result["Category"].iloc[0] == "takeout"

    def test_global_rules_apply_when_no_extra_rule_matches(
        self, rules_bank_config, output_config, rules_config
    ):
        """When extra_rules don't match, global rules still fire normally."""
        rules_bank_config.extra_rules = [
            {
                "name": "bank_specific",
                "regex": "hausbank",
                "match_on": "Description",
                "set": {"Category": "transit"},
            }
        ]
        processor = CSVProcessor(
            rules_bank_config,
            output_config,
            "YYYY-MM-DD",
            rules_config=rules_config,
        )
        result = processor.process(b"Date;Description\n01.01.26;REWE MARKT")
        # extra_rule did not match; global groceries rule fires
        assert result["Category"].iloc[0] == "groceries"


class TestApplyRulesShortenDescription:
    """shorten_description_on_rule_match bank-level flag."""

    def test_description_shortened_to_matched_text(
        self, rules_bank_config, output_config, rules_config
    ):
        """When flag is set, Description is replaced with the matched keyword."""
        rules_bank_config.shorten_description_on_rule_match = True
        processor = CSVProcessor(
            rules_bank_config,
            output_config,
            "YYYY-MM-DD",
            rules_config=rules_config,
        )
        result = processor.process(
            b"Date;Description\n01.01.26;REWE MARKT GMBH 1234"
        )
        assert result["Description"].iloc[0] == "rewe"
        assert result["Category"].iloc[0] == "groceries"

    def test_unmatched_row_description_unchanged(
        self, rules_bank_config, output_config, rules_config
    ):
        """Rows without a matching rule keep their full description."""
        rules_bank_config.shorten_description_on_rule_match = True
        processor = CSVProcessor(
            rules_bank_config,
            output_config,
            "YYYY-MM-DD",
            rules_config=rules_config,
        )
        result = processor.process(
            b"Date;Description\n01.01.26;UNKNOWN STORE XYZ"
        )
        assert result["Description"].iloc[0] == "unknown store xyz"

    def test_flag_off_description_not_shortened(
        self, rules_bank_config, output_config, rules_config
    ):
        """Without the flag, Description is never shortened even when a rule matches."""
        # flag is absent (default) in rules_bank_config
        processor = CSVProcessor(
            rules_bank_config,
            output_config,
            "YYYY-MM-DD",
            rules_config=rules_config,
        )
        result = processor.process(
            b"Date;Description\n01.01.26;REWE MARKT GMBH 1234"
        )
        assert result["Description"].iloc[0] == "rewe markt gmbh 1234"
        assert result["Category"].iloc[0] == "groceries"


class TestApplyRulesEdgeCases:
    """Robustness: invalid regexes, missing columns, empty rule lists."""

    def test_invalid_regex_warns_and_falls_through_to_next_rule(
        self, rules_bank_config, output_config
    ):
        """Invalid regex emits SyntaxWarning at construction time and is skipped;
        subsequent valid rules still fire normally."""
        rules = OmegaConf.create(
            {
                "rules": [
                    {
                        "name": "bad",
                        "regex": "[unclosed",
                        "match_on": "Description",
                        "set": {"Category": "invalid"},
                    },
                    {
                        "name": "good",
                        "regex": "rewe",
                        "match_on": "Description",
                        "set": {"Category": "groceries"},
                    },
                ]
            }
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            processor = CSVProcessor(
                rules_bank_config,
                output_config,
                "YYYY-MM-DD",
                rules_config=rules,
            )
            result = processor.process(b"Date;Description\n01.01.26;REWE MARKT")

        assert result["Category"].iloc[0] == "groceries"
        assert any(issubclass(w.category, SyntaxWarning) for w in caught)

    def test_nonexistent_match_on_column_is_skipped(
        self, rules_bank_config, output_config
    ):
        """A rule targeting a column that doesn't exist in output is silently ignored."""
        rules = OmegaConf.create(
            {
                "rules": [
                    {
                        "name": "bad_col",
                        "regex": "rewe",
                        "match_on": "NonExistentColumn",
                        "set": {"Category": "groceries"},
                    }
                ]
            }
        )
        processor = CSVProcessor(
            rules_bank_config, output_config, "YYYY-MM-DD", rules_config=rules
        )
        result = processor.process(b"Date;Description\n01.01.26;REWE MARKT")
        # Rule skipped → default stays
        assert result["Category"].iloc[0] == "household"

    def test_empty_rules_list_no_change(self, rules_bank_config, output_config):
        """An empty rules list leaves all values at their defaults."""
        rules = OmegaConf.create({"rules": []})
        processor = CSVProcessor(
            rules_bank_config, output_config, "YYYY-MM-DD", rules_config=rules
        )
        result = processor.process(b"Date;Description\n01.01.26;REWE MARKT")
        assert result["Category"].iloc[0] == "household"

    def test_rule_with_empty_set_does_not_crash(
        self, rules_bank_config, output_config
    ):
        """A rule with an empty set dict is a no-op and does not raise."""
        rules = OmegaConf.create(
            {
                "rules": [
                    {
                        "name": "noop",
                        "regex": "rewe",
                        "match_on": "Description",
                        "set": {},
                    }
                ]
            }
        )
        processor = CSVProcessor(
            rules_bank_config, output_config, "YYYY-MM-DD", rules_config=rules
        )
        result = processor.process(b"Date;Description\n01.01.26;REWE MARKT")
        assert result["Category"].iloc[0] == "household"


class TestRemapValues:
    """remap_values bank-level config: post-rule value substitution."""

    def test_literal_joint_remapped_to_to_be_split(
        self, rules_bank_config, output_config
    ):
        """Payment 'joint' (set by literal) is remapped to 'to be split'."""
        rules_bank_config.remap_values = {"Payment": {"joint": "to be split"}}
        processor = CSVProcessor(rules_bank_config, output_config, "YYYY-MM-DD")
        result = processor.process(b"Date;Description\n01.01.26;UNKNOWN STORE")
        assert result["Payment"].iloc[0] == "to be split"

    def test_rule_set_joint_remapped(self, rules_bank_config, output_config):
        """Payment 'joint' set by a rule is also remapped."""
        rules = OmegaConf.create(
            {
                "rules": [
                    {
                        "name": "force_joint",
                        "regex": "rewe",
                        "match_on": "Description",
                        "set": {"Payment": "joint"},
                    }
                ]
            }
        )
        rules_bank_config.remap_values = {"Payment": {"joint": "to be split"}}
        processor = CSVProcessor(
            rules_bank_config, output_config, "YYYY-MM-DD", rules_config=rules
        )
        result = processor.process(b"Date;Description\n01.01.26;REWE MARKT")
        assert result["Payment"].iloc[0] == "to be split"

    def test_non_matching_value_untouched(
        self, rules_bank_config, output_config
    ):
        """Values that don't match a remap entry are left unchanged."""
        rules_bank_config.column_mappings.Payment.value = "direct"
        rules_bank_config.remap_values = {"Payment": {"joint": "to be split"}}
        processor = CSVProcessor(rules_bank_config, output_config, "YYYY-MM-DD")
        result = processor.process(b"Date;Description\n01.01.26;UNKNOWN STORE")
        assert result["Payment"].iloc[0] == "direct"

    def test_remap_multiple_columns(self, rules_bank_config, output_config):
        """remap_values can target multiple columns in one config entry."""
        rules_bank_config.remap_values = {
            "Payment": {"joint": "to be split"},
            "Payer": {"john": "alex"},
        }
        processor = CSVProcessor(rules_bank_config, output_config, "YYYY-MM-DD")
        result = processor.process(b"Date;Description\n01.01.26;UNKNOWN STORE")
        assert result["Payment"].iloc[0] == "to be split"
        assert result["Payer"].iloc[0] == "alex"

    def test_no_remap_values_key_no_change(
        self, rules_bank_config, output_config
    ):
        """Without remap_values in bank config, all values stay as-is."""
        # rules_bank_config has no remap_values key by default
        processor = CSVProcessor(rules_bank_config, output_config, "YYYY-MM-DD")
        result = processor.process(b"Date;Description\n01.01.26;UNKNOWN STORE")
        assert result["Payment"].iloc[0] == "joint"

    def test_nonexistent_column_is_ignored(
        self, rules_bank_config, output_config
    ):
        """remap_values referencing a column absent from the output is silently skipped."""
        rules_bank_config.remap_values = {
            "NonExistent": {"joint": "to be split"}
        }
        processor = CSVProcessor(rules_bank_config, output_config, "YYYY-MM-DD")
        # Should not raise
        result = processor.process(b"Date;Description\n01.01.26;UNKNOWN STORE")
        assert result["Payment"].iloc[0] == "joint"

    def test_remap_applied_after_rules(
        self, rules_bank_config, output_config, rules_config
    ):
        """remap_values fires after rules, so rule-set values are also remapped."""
        # rent rule sets Payment to "direct" — remap should NOT touch it
        # because "direct" != "joint"
        rules_bank_config.remap_values = {"Payment": {"joint": "to be split"}}
        processor = CSVProcessor(
            rules_bank_config,
            output_config,
            "YYYY-MM-DD",
            rules_config=rules_config,
        )
        result = processor.process(b"Date;Description\n01.01.26;MIETE JANUAR")
        # rent rule sets Payment = "direct"; remap doesn't touch "direct"
        assert result["Payment"].iloc[0] == "direct"

    def test_all_rows_remapped(self, rules_bank_config, output_config):
        """Every row with the old value is remapped, not just the first."""
        rules_bank_config.remap_values = {"Payment": {"joint": "to be split"}}
        processor = CSVProcessor(rules_bank_config, output_config, "YYYY-MM-DD")
        csv = (
            b"Date;Description\n"
            b"01.01.26;STORE A\n"
            b"02.01.26;STORE B\n"
            b"03.01.26;STORE C"
        )
        result = processor.process(csv)
        assert all(v == "to be split" for v in result["Payment"].tolist())
