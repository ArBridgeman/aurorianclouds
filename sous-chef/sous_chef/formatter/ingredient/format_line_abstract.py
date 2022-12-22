from dataclasses import dataclass
from fractions import Fraction

import regex
from abstract.extended_enum import ExtendedEnum
from pint import Unit
from sous_chef.formatter.format_unit import UnitExtractionError, UnitFormatter


@dataclass
class LineParsingError(Exception):
    line: str
    message: str = "[line parsing failed]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message} text={self.line}"


class MapLineErrorToException(ExtendedEnum):
    ingredient_line_parsing_error = LineParsingError


@dataclass
class LineFormatter:
    line: str
    line_format_dict: dict
    unit_formatter: UnitFormatter
    quantity: str = None
    fraction: str = None
    quantity_float: float = 0.0
    unit: str = None
    pint_unit: Unit = None
    item: str = None

    def __post_init__(self):
        # replace BOM character
        self.line = self.line.replace("\ufeff", "").strip()
        self._extract_field_list_from_line()

    def _set_quantity_float(self):
        if self.quantity:
            self.quantity_float += float(self.quantity)
        if self.fraction:
            self.quantity_float += float(Fraction(self.fraction))
        if not self.quantity_float:
            self.quantity_float = 1.0

    def _extract_field_list_from_line(self):
        unit_with_ingredient = self.line_format_dict["unit_with_ingredient"]
        for prefix_type in self.line_format_dict["prefix_pattern"]:
            format_group = self.line_format_dict[prefix_type]
            pattern = format_group.pattern + unit_with_ingredient
            result = regex.match(pattern, self.line)
            if result is not None:
                [
                    self.__setattr__(group, result.group(index + 1))
                    for index, group in enumerate(format_group.group)
                ]
                return
        raise LineParsingError(line=self.line)

    def _split_item_and_unit(self):
        # TODO replace with NER/NLP or make more general
        text_split = self.item.split(" ")
        if len(text_split) >= 1:
            try:
                text_unit = text_split[0]
                unit, pint_unit = self.unit_formatter.extract_unit_from_text(
                    text_unit
                )
                self.pint_unit = pint_unit
                self.unit = unit
                self.item = " ".join(text_split[1:])
            # expected as data often lacks units
            except UnitExtractionError:
                pass
            finally:
                self.item = self.item.strip()
