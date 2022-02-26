from dataclasses import dataclass

from sous_chef.formatter.ingredient.format_line_abstract import LineFormatter
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
class NoTitleReferencedRecipeError(Exception):
    referenced_recipe: ReferencedRecipe
    message: str = "[empty title]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return (
            f"{self.message} referenced_recipe={self.referenced_recipe.title}"
        )


@dataclass
class ReferencedRecipeLine(LineFormatter):
    # TODO should recipe book be here instead?
    def convert_to_referenced_recipe(self) -> ReferencedRecipe:
        self._set_quantity_float()
        self._split_item_and_unit()
        self._remove_unit_override_quantity()

        referenced_recipe = ReferencedRecipe(
            quantity=self.quantity_float, title=self.item
        )
        if len(referenced_recipe.title) == 0:
            raise NoTitleReferencedRecipeError(
                referenced_recipe=referenced_recipe
            )
        return referenced_recipe

    def _remove_unit_override_quantity(self):
        # TODO properly implement with quantity & units
        if self.unit is not None:
            FILE_LOGGER.warning(
                "[not implemented] unit-specified reference recipes."
                "Override factor=1",
                item=self.item,
                unit=self.unit,
            )
            self.unit = None
            self.quantity_float = 1
