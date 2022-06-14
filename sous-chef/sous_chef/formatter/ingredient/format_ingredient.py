from dataclasses import dataclass

import pandas as pd
import regex
from omegaconf import DictConfig
from pint import Unit
from sous_chef.abstract.search_dataframe import FuzzySearchError
from sous_chef.formatter.format_unit import UnitFormatter
from sous_chef.formatter.ingredient.format_line_abstract import LineFormatter
from sous_chef.formatter.ingredient.format_referenced_recipe import (
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
    barcode: str = None
    recipe_uuid: str = None

    def set_pantry_info(self, pantry_item: pd.Series):
        self.item = pantry_item.true_ingredient
        self.is_staple = pantry_item.is_staple
        self.group = pantry_item.group
        self.item_plural = pantry_item.item_plural
        self.store = pantry_item.store
        self.factor *= pantry_item.replace_factor
        self.barcode = pantry_item.barcode
        self.recipe_uuid = pantry_item.recipe_uuid


@dataclass
class IngredientLine(LineFormatter):
    # TODO re-add optional check
    is_optional: bool = False
    instruction: str = None

    def convert_to_ingredient(self) -> Ingredient:
        self._set_quantity_float()
        self._split_item_and_unit()
        self._split_item_instruction()
        ingredient = Ingredient(
            quantity=self.quantity_float,
            unit=self.unit,
            pint_unit=self.pint_unit,
            item=self.item,
        )
        if len(ingredient.item) == 0:
            raise EmptyIngredientError(ingredient=ingredient)
        return ingredient

    def _split_item_instruction(self):
        # TODO change so that reformats ingredients to be (chopped)
        # TODO have verbs in config instead or NLP/NER-solution
        # TODO likely need to treat shredded differently
        for verb in ["chopped", "minced", "diced"]:
            if verb in self.item:
                self.item = self.item.replace(verb, "").strip()
                self.instruction = verb


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
class BadIngredientError(IngredientError):
    message: str = "[bad ingredient]"


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
        self._enrich_with_pantry_detail(ingredient)
        return ingredient

    def format_manual_ingredient(
        self, quantity: float, unit: str, item: str
    ) -> Ingredient:
        pint_unit = None
        if isinstance(unit, str) and unit != "":
            unit, pint_unit = self.unit_formatter.extract_unit_from_text(unit)
        ingredient = Ingredient(
            quantity=quantity, unit=unit, pint_unit=pint_unit, item=item
        )
        self._enrich_with_pantry_detail(ingredient)
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
        match = regex.match(r"^\[[\w+\s]+\]$", ingredient_line)
        return match is not None

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
        # TODO do we want to add a custom exception here instead of None?
        if len(ingredient_line) > self.config.min_line_length:
            return ingredient_line

    def _enrich_with_pantry_detail(self, ingredient: Ingredient):
        try:
            pantry_item = self.pantry_list.retrieve_match(
                "ingredient", ingredient.item
            )

            if pantry_item.label == "bad_ingredient":
                raise BadIngredientError(ingredient=ingredient)

            ingredient.set_pantry_info(pantry_item)

            if pantry_item.replace_unit != "" and ingredient.unit is None:
                (
                    ingredient.unit,
                    ingredient.pint_unit,
                ) = self.unit_formatter.extract_unit_from_text(
                    pantry_item.replace_unit
                )

        except FuzzySearchError:
            raise PantrySearchError(ingredient=ingredient)
