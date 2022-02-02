from dataclasses import dataclass

from sous_chef.formatter.ingredient._format_line_abstract import LineFormatter
from structlog import get_logger

FILE_LOGGER = get_logger(__name__)


@dataclass
class ReferencedRecipe:
    quantity: float
    title: str
    # TODO to implement
    # unit: str = None
    # pint_unit: Unit = None


@dataclass
class ReferencedRecipeLine(LineFormatter):
    # TODO should recipe book be here? not in grocery list
    def __post_init__(self):
        self._extract_field_list_from_line()

    def convert_to_referenced_recipe(self) -> ReferencedRecipe:
        self._set_quantity_float()
        self._split_item_and_unit()
        self._remove_unit_override_quantity()
        return ReferencedRecipe(quantity=self.quantity_float, title=self.item)

    def _remove_unit_override_quantity(self):
        # TODO properly implement with quantity & units
        if self.unit:
            FILE_LOGGER.warning(
                "[not implemented] unit-specified reference recipes."
                "Override factor=1",
                item=self.item,
                unit=self.unit,
            )
