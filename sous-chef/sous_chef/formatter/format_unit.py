from dataclasses import dataclass

from pint import DimensionalityError, Quantity, UndefinedUnitError, Unit
from sous_chef.formatter.units import (
    allowed_unit_list,
    not_abbreviated,
    unit_registry,
)
from structlog import get_logger

FILE_LOGGER = get_logger(__name__)


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
    @staticmethod
    def convert_to_desired_unit(
        quantity: float, pint_unit: Unit, desired_pint_unit: Unit
    ) -> (float, Unit):
        original_value = quantity * pint_unit
        converted_value = original_value.to(desired_pint_unit)

        # round to significant digits per defined unit_registry
        converted_quantity = round(converted_value.magnitude, 2)
        converted_pint_unit = converted_value.units
        return converted_quantity, converted_pint_unit

    def get_unit_str(self, quantity: float, unit: Unit) -> str:
        # TODO more robust way to do? e.g. inflection or define
        if quantity > 1 and unit in not_abbreviated:
            return f"{unit}s"
        return self.get_unit_as_abbreviated_str(unit)

    @staticmethod
    def get_pint_unit(text_unit: str) -> Unit:
        return get_pint_repr(text_unit).units

    @staticmethod
    def get_unit_as_abbreviated_str(pint_unit: Unit) -> str:
        if pint_unit == unit_registry.dimensionless:
            return ""

        if pint_unit in not_abbreviated:
            return str(pint_unit)

        return "{:~}".format(pint_unit)


def get_pint_repr(text_with_unit: str) -> Quantity:
    try:
        pint_repr = unit_registry.parse_expression(text_with_unit.casefold())
        if (pint_unit := pint_repr.units) in allowed_unit_list:
            return pint_repr
        FILE_LOGGER.warning(
            "[get pint unit]",
            warn="unit not in allowed_unit_list",
            unit=pint_unit,
        )
    except (AttributeError, DimensionalityError, UndefinedUnitError):
        pass
    raise UnitExtractionError(text=text_with_unit)
