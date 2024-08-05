from dataclasses import dataclass
from typing import List, Tuple

from omegaconf import DictConfig
from pint import Unit
from sous_chef.abstract.extended_enum import ExtendedEnum, extend_enum
from sous_chef.abstract.handle_exception import BaseWithExceptionHandling
from sous_chef.formatter.format_unit import UnitFormatter
from sous_chef.formatter.ingredient.format_ingredient import (
    Ingredient,
    IngredientFormatter,
    MapIngredientErrorToException,
)
from sous_chef.formatter.ingredient.format_line_abstract import (
    MapLineErrorToException,
)
from sous_chef.formatter.units import unit_registry
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from sous_chef.recipe_book.recipe_util import (
    MapRecipeErrorToException,
    RecipeSchema,
)
from structlog import get_logger

FILE_LOGGER = get_logger(__name__)


@dataclass
class ReferencedRecipeDimensionalityError(Exception):
    source_recipe_title: str
    source_needed_unit: Unit
    referenced_recipe_title: str
    referenced_recipe_unit: Unit
    message: str = "[referenced recipe dimensionality does not match]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return (
            f"{self.message} base_recipe={self.source_recipe_title}"
            f"(unit: {self.source_needed_unit}) not "
            f"compatible with referenced_recipe={self.referenced_recipe_title} "
            f"(unit: {self.referenced_recipe_unit})"
        )


class MapReferencedRecipeToException(ExtendedEnum):
    recipe_dimensionality_incompatibility = ReferencedRecipeDimensionalityError


@extend_enum(
    [
        MapIngredientErrorToException,
        MapLineErrorToException,
        MapRecipeErrorToException,
        MapReferencedRecipeToException,
    ]
)
class MapIngredientFieldErrorToException(ExtendedEnum):
    pass


@dataclass
class IngredientField(BaseWithExceptionHandling):
    config: DictConfig
    ingredient_formatter: IngredientFormatter
    recipe_book: RecipeBook
    ingredient_list: List = None
    referenced_recipe_list: List = None

    def __post_init__(self):
        self.set_tuple_log_and_skip_exception_from_config(
            config_errors=self.config.errors,
            exception_mapper=MapIngredientFieldErrorToException,
        )

    def parse_ingredient_field(
        self, recipe: RecipeSchema
    ) -> Tuple[List[RecipeSchema], List[Ingredient], List]:
        self.referenced_recipe_list = []
        self.ingredient_list = []
        self.record_exception = []
        is_in_optional_group = False
        for line in recipe.ingredients.split("\n"):
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
                self._format_referenced_recipe(
                    source_recipe_title=recipe.title, line=stripped_line
                )
            else:
                self._format_ingredient(stripped_line, is_in_optional_group)

        return (
            self.referenced_recipe_list,
            self.ingredient_list,
            self.record_exception,
        )

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def _format_referenced_recipe(self, source_recipe_title: str, line: str):
        needed_ref_recipe = self.ingredient_formatter.format_referenced_recipe(
            line
        )
        ref_recipe = self.recipe_book.get_recipe_by_title(
            needed_ref_recipe.title
        )

        if needed_ref_recipe.pint_unit != unit_registry.dimensionless:
            if (
                ref_recipe.quantity.units.dimensionality
                == needed_ref_recipe.pint_unit.dimensionality
            ):
                (
                    needed_ref_quantity,
                    needed_ref_units,
                ) = UnitFormatter.convert_to_desired_unit(
                    needed_ref_recipe.quantity,
                    needed_ref_recipe.pint_unit,
                    ref_recipe.quantity.units,
                )
                factor_dimensionless = (
                    needed_ref_quantity * needed_ref_units / ref_recipe.quantity
                )

                ref_recipe.factor = factor_dimensionless.magnitude
                ref_recipe.amount = needed_ref_recipe.amount
                self.referenced_recipe_list.append(ref_recipe)
                return
            raise ReferencedRecipeDimensionalityError(
                source_recipe_title=source_recipe_title,
                source_needed_unit=needed_ref_recipe.pint_unit,
                referenced_recipe_title=ref_recipe.title,
                referenced_recipe_unit=ref_recipe.quantity.units,
            )

        # case without units should just be multiplication
        ref_recipe.factor *= needed_ref_recipe.quantity
        ref_recipe.amount = needed_ref_recipe.amount
        self.referenced_recipe_list.append(ref_recipe)

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
