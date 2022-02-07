import re
from dataclasses import dataclass
from typing import List

from omegaconf import DictConfig
from pint import Unit, UnitRegistry

# each subsequent one is * 10 greater
METRIC_MACRO_PREFIX = ["da", "h", "k", "M"]
# each subsequent one is / 10 lesser
METRIC_MICRO_PREFIX = ["d", "c", "m"]
METRIC_BASE = [""]

REGEX_UNIT_TEXT = r"^\s*{}\s+"

unit_registry = UnitRegistry()
unit_registry.default_format = ".2f"


@dataclass
class UnitExtractionError(Exception):
    text: str
    message: str = "[unit extraction failed]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message} text={self.text}"


@dataclass
class UnitFormatter:
    config: DictConfig

    def __post_init__(self):
        self.standard_unit_list = self._get_standard_unit_list()
        self.dimensionless_list = list(self.config.undefined)

    def extract_unit_from_text(self, text: str) -> (str, Unit):
        for unit in self.standard_unit_list:
            result = re.match(REGEX_UNIT_TEXT.format(unit), text)
            if result is not None:
                return unit, get_pint_unit(unit)

        for unit in self.dimensionless_list:
            result = re.match(REGEX_UNIT_TEXT.format(unit), text)
            if result is not None:
                return unit, None

        raise UnitExtractionError(text=text)

    def _get_standard_unit_list(self) -> List[str]:
        metric = self._get_all_relevant_metric_units()
        return metric + list(self.config.empirical)

    def _get_all_relevant_metric_units(self) -> List[str]:
        return [
            f"{prefix}{unit}"
            for prefix in METRIC_BASE
            + METRIC_MACRO_PREFIX
            + METRIC_MICRO_PREFIX
            for unit in self.config.metric
        ]


def convert_quantity_to_desired_unit(
    quantity: float, unit: Unit, desired_unit: Unit
) -> (float, Unit):
    original_value = quantity * unit
    converted_value = original_value.to(desired_unit)
    # round to significant digits per defined unit_registry
    return round(converted_value.magnitude, 2), converted_value.units


def get_pint_unit(unit: str):
    return unit_registry.parse_expression(unit).units


def get_unit_as_abbreviated_str(unit: Unit) -> str:
    abbreviation = "{:~}".format(unit)
    if abbreviation == "cp":
        return "cup"
    return abbreviation
