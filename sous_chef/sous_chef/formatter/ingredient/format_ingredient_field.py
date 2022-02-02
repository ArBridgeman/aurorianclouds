from dataclasses import dataclass

from omegaconf import DictConfig
from sous_chef.formatter.ingredient.format_ingredient import (
    EmptyIngredientError,
    IngredientError,
    IngredientFormatter,
    PantrySearchError,
    SkipIngredientError,
)
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from structlog import get_logger

FILE_LOGGER = get_logger(__name__)


def raise_or_log_exception(raise_exception: bool, exception: Exception):
    if raise_exception:
        raise exception
    else:
        FILE_LOGGER.error(str(exception))


@dataclass
class IngredientFieldFormatter:
    config: DictConfig
    ingredient_formatter: IngredientFormatter
    recipe_book: RecipeBook
    # TODO find pep-acceptable way to do
    ingredient_list = []
    referenced_recipe_list = []

    def parse_ingredient_field(self, ingredient_field):
        self._create_empty_queues()
        is_in_optional_group = False
        for line in ingredient_field.split("\n"):
            stripped_line = self.ingredient_formatter.strip_line(line)

            if stripped_line is None:
                continue
            elif self.ingredient_formatter.is_group(stripped_line):
                is_in_optional_group = (
                    self.ingredient_formatter.is_optional_group(stripped_line)
                )
                continue
            elif stripped_line.startswith("#"):
                self._format_referenced_recipe_to_recipe(stripped_line)
            else:
                self._format_ingredient(stripped_line, is_in_optional_group)

        return self.referenced_recipe_list, self.ingredient_list

    def _create_empty_queues(self):
        self.ingredient_list = []
        self.referenced_recipe_list = []

    def _format_referenced_recipe_to_recipe(self, line: str):
        referenced_recipe = self.ingredient_formatter.format_referenced_recipe(
            line
        )
        recipe = self.recipe_book.get_recipe_by_title(referenced_recipe.title)
        recipe.factor *= referenced_recipe.quantity
        self.referenced_recipe_list.append(recipe)

    def _format_ingredient_line(self, line: str, is_in_optional_group: bool):
        ingredient = self.ingredient_formatter.format_ingredient_line(
            ingredient_line=line,
        )
        if not ingredient.is_optional:
            setattr(ingredient, "is_optional", is_in_optional_group)
        return ingredient

    def _format_ingredient(self, line: str, is_in_optional_group: bool):
        try:
            ingredient = self._format_ingredient_line(
                line, is_in_optional_group
            )
            self.ingredient_list.append(ingredient)
        except EmptyIngredientError as e:
            self._handle_ingredient_exception(self.config.empty_ingredient, e)
        except PantrySearchError as e:
            self._handle_ingredient_exception(self.config.pantry_search, e)
        except SkipIngredientError as e:
            self._handle_ingredient_exception(self.config.skip_ingredient, e)

    def _handle_ingredient_exception(
        self, error_config: DictConfig, error: IngredientError
    ):
        raise_or_log_exception(error_config.raise_error_for, error)
        if error_config.still_add_ingredient:
            FILE_LOGGER.warning(
                "[ignore error]",
                action="still add to list",
                ingredient=error.ingredient.item,
            )
            self.ingredient_list.append(error.ingredient)
