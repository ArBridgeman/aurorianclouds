from dataclasses import dataclass

from pint import Unit
from pydantic import BaseModel
from sous_chef.formatter.ingredient.format_line_abstract import LineFormatter
from structlog import get_logger

FILE_LOGGER = get_logger(__name__)


class ReferencedRecipe(BaseModel):
    quantity: float
    pint_unit: Unit
    title: str
    amount: str

    class Config:
        arbitrary_types_allowed: bool = True


@dataclass
class NoTitleReferencedRecipeError(Exception):
    referenced_recipe_title: str
    message: str = "[empty title]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return (
            f"{self.message} referenced_recipe={self.referenced_recipe_title}"
        )


@dataclass
class ReferencedRecipeLine(LineFormatter):
    def convert_to_referenced_recipe(self) -> ReferencedRecipe:
        self._set_quantity_float()
        self._split_item_and_unit()

        if len(self.item) == 0:
            raise NoTitleReferencedRecipeError(self.item)

        return ReferencedRecipe(
            quantity=self.quantity_float,
            pint_unit=self.pint_unit,
            title=self.item,
            amount=self.line,
        )
