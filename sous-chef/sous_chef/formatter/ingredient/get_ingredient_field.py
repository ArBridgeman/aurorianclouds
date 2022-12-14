from dataclasses import dataclass
from typing import List

from omegaconf import DictConfig
from sous_chef.abstract.handle_exception import BaseWithExceptionHandling
from sous_chef.formatter.ingredient.format_ingredient import IngredientFormatter
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from structlog import get_logger

FILE_LOGGER = get_logger(__name__)


@dataclass
class IngredientField(BaseWithExceptionHandling):
    config: DictConfig
    ingredient_formatter: IngredientFormatter
    recipe_book: RecipeBook
    ingredient_list: List = None
    referenced_recipe_list: List = None

    def __post_init__(self):
        self.set_tuple_log_and_skip_exception_from_config(self.config.errors)

    def parse_ingredient_field(self, ingredient_field):
        self.ingredient_list = []
        self.record_exception = []
        self.referenced_recipe_list = []
        is_in_optional_group = False
        for line in ingredient_field.split("\n"):
            stripped_line = self.ingredient_formatter.strip_line(line)

            if stripped_line is None:
                continue
            elif self.ingredient_formatter.is_ignored_entry(stripped_line):
                continue
            elif self.ingredient_formatter.is_group(stripped_line):
                is_in_optional_group = (
                    self.ingredient_formatter.is_optional_group(stripped_line)
                )
                continue
            elif stripped_line.startswith("#"):
                self._format_referenced_recipe(stripped_line)
            else:
                self._format_ingredient(stripped_line, is_in_optional_group)

        return self.referenced_recipe_list, self.ingredient_list

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def _format_referenced_recipe(self, line: str):
        referenced_recipe = self.ingredient_formatter.format_referenced_recipe(
            line
        )
        recipe = self.recipe_book.get_recipe_by_title(referenced_recipe.title)
        recipe.factor *= referenced_recipe.quantity
        recipe.amount = referenced_recipe.amount
        self.referenced_recipe_list.append(recipe)

    def _format_ingredient_line(self, line: str, is_in_optional_group: bool):
        ingredient = self.ingredient_formatter.format_ingredient_line(
            ingredient_line=line,
        )
        if not ingredient.is_optional:
            setattr(ingredient, "is_optional", is_in_optional_group)
        return ingredient

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def _format_ingredient(self, line: str, is_in_optional_group: bool):
        ingredient = self._format_ingredient_line(line, is_in_optional_group)
        self.ingredient_list.append(ingredient)
