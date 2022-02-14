from dataclasses import dataclass

from pint import UndefinedUnitError, Unit
from sous_chef.formatter.units import allowed_unit_list, unit_registry


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
    def extract_unit_from_text(self, text_unit: str) -> (str, Unit):
        pint_unit = self._get_pint_unit(text_unit)
        true_unit = self._get_unit_as_abbreviated_str(pint_unit)
        return true_unit, pint_unit

    @staticmethod
    def _get_pint_unit(text_unit: str):
        try:
            pint_unit = unit_registry.parse_expression(text_unit).units
            if pint_unit in allowed_unit_list:
                return pint_unit
        except UndefinedUnitError:
            pass
        raise UnitExtractionError(text=text_unit)

    def convert_to_desired_unit(
        self, quantity: float, pint_unit: Unit, desired_pint_unit: Unit
    ) -> (float, str, Unit):
        original_value = quantity * pint_unit
        converted_value = original_value.to(desired_pint_unit)

        # round to significant digits per defined unit_registry
        converted_quantity = round(converted_value.magnitude, 2)
        converted_pint_unit = converted_value.units
        converted_unit = self._get_unit_as_abbreviated_str(
            converted_value.units
        )
        return converted_quantity, converted_unit, converted_pint_unit

    @staticmethod
    def _get_unit_as_abbreviated_str(unit: Unit) -> str:
        abbreviation = "{:~}".format(unit)
        if abbreviation == "cp":
            return "cup"
        return abbreviation
