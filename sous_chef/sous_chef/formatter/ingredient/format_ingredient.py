from dataclasses import dataclass

import pandas as pd
import regex
from omegaconf import DictConfig
from pint import Unit
from sous_chef.abstract.search_dataframe import FuzzySearchError
from sous_chef.formatter.format_unit import UnitFormatter
from sous_chef.formatter.ingredient._format_line_abstract import LineFormatter
from sous_chef.formatter.ingredient._format_line_referenced_recipe import (
    ReferencedRecipe,
    ReferencedRecipeLine,
)
from sous_chef.pantry_list.read_pantry_list import PantryList
from structlog import get_logger

FILE_LOGGER = get_logger(__name__)


@dataclass
class Ingredient:
    quantity: float
    item: str
    factor: float = 1.0
    is_optional: bool = False
    is_staple: bool = False
    unit: str = None
    pint_unit: Unit = None
    group: str = None
    item_plural: str = None
    store: str = None
    should_skip: bool = False

    def set_pantry_info(self, pantry_item: pd.Series):
        self.item = pantry_item.true_ingredient
        # TODO (grocery_list) make if not grocery store go to other section
        self.is_staple = pantry_item.is_staple
        self.group = pantry_item.group
        self.item_plural = pantry_item.item_plural
        self.store = pantry_item.store
        self.should_skip = pantry_item.skip == "Y"


@dataclass
class IngredientLine(LineFormatter):
    # TODO re-add optional check
    is_optional: bool = False

    def __post_init__(self):
        self._extract_field_list_from_line()

    def convert_to_ingredient(self) -> Ingredient:
        self._set_quantity_float()
        self._split_item_and_unit()
        self._format_item()
        ingredient = Ingredient(
            quantity=self.quantity_float,
            unit=self.unit,
            pint_unit=self.pint_unit,
            item=self.item,
        )
        if len(ingredient.item) == 0:
            raise EmptyIngredientError(ingredient=ingredient)
        return ingredient

    def _format_item(self):
        self._remove_instruction()

    def _remove_instruction(self):
        # TODO change so that reformats ingredients to be (chopped)
        # TODO have verbs in config instead
        # TODO likely need to treat shredded differently
        for verbs in ["chopped", "minced", "diced"]:
            self.item = self.item.replace(verbs, "")


@dataclass
class IngredientError(Exception):
    ingredient: Ingredient
    message: str

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message} ingredient={self.ingredient.item}"


@dataclass
class EmptyIngredientError(IngredientError):
    message: str = "[empty ingredient]"


@dataclass
class PantrySearchError(IngredientError):
    message: str = "[pantry search failed]"


@dataclass
class SkipIngredientError(IngredientError):
    message: str = "[skip ingredient]"


@dataclass
class IngredientFormatter:
    config: DictConfig
    pantry_list: PantryList
    unit_formatter: UnitFormatter

    def format_ingredient_line(
        self,
        ingredient_line: str,
    ) -> Ingredient:
        ingredient_line = IngredientLine(
            ingredient_line,
            self.config.ingredient_line_format,
            self.unit_formatter,
        )
        ingredient = ingredient_line.convert_to_ingredient()
        self._enrich_with_pantry_information(ingredient)
        return ingredient

    def format_manual_ingredient(
        self, quantity: float, unit: str, item: str
    ) -> Ingredient:
        ingredient = Ingredient(quantity=quantity, unit=unit, item=item)
        self._enrich_with_pantry_information(ingredient)
        return ingredient

    def format_referenced_recipe(self, recipe_line: str) -> ReferencedRecipe:
        recipe_line = ReferencedRecipeLine(
            recipe_line,
            self.config.referenced_recipe_format,
            self.unit_formatter,
        )
        return recipe_line.convert_to_referenced_recipe()

    @staticmethod
    def is_group(ingredient_line: str):
        return "[" in ingredient_line

    @staticmethod
    def is_optional_group(ingredient_line: str):
        # TODO put into config as tuple?
        return ingredient_line.casefold() in [
            "[recommended sides]",
            "[sides]",
            "[optional]",
            "[garnish]",
        ]

    def strip_line(self, raw_ingredient_line: str):
        ingredient_line = regex.sub(r"\s+", " ", raw_ingredient_line.strip())
        if len(ingredient_line) > self.config.min_line_length:
            return ingredient_line

    def _enrich_with_pantry_information(self, ingredient: Ingredient):
        try:
            pantry_item = (
                self.pantry_list.retrieve_direct_match_or_fuzzy_fallback(
                    "ingredient", ingredient.item
                )
            )
            ingredient.set_pantry_info(pantry_item)
        except FuzzySearchError:
            raise PantrySearchError(ingredient=ingredient)

        if ingredient.should_skip:
            raise SkipIngredientError(ingredient=ingredient)
