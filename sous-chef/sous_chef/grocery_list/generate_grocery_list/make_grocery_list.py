from dataclasses import dataclass
from datetime import date, timedelta
from typing import Tuple

import pandas as pd
from omegaconf import DictConfig
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.formatter.format_unit import UnitFormatter
from sous_chef.formatter.ingredient.format_ingredient import IngredientFormatter
from sous_chef.formatter.ingredient.get_ingredient_field import IngredientField
from sous_chef.grocery_list.generate_grocery_list.generate_grocery_list import (
    GroceryListOld,
)
from sous_chef.menu.create_menu.create_menu import Menu
from sous_chef.pantry_list.read_pantry_list import PantryList
from sous_chef.recipe_book.read_recipe_book import RecipeBook

from utilities.api.gsheets_api import GsheetsHelper
from utilities.api.todoist_api import TodoistHelper


@dataclass
class GroceryList:
    def __init__(self, config: DictConfig):
        self.config = config

        # share services
        self.due_date_formatter = DueDatetimeFormatter(
            config=self.config.date.due_date
        )
        self.unit_formatter = UnitFormatter()

        # shared attributes
        self.primary_shopping_date = self._set_primary_shopping_date()
        self.secondary_shopping_date = None
        self.second_shopping_day_group = ()
        if self.config.grocery_list.shopping.secondary_day:
            self._set_secondary_shopping_info()
        calendar_week = self.due_date_formatter.get_calendar_week()
        self.app_week_label = f"app-week-{calendar_week}"

    def _get_ingredient_field(self) -> IngredientField:
        ingredient_formatter = IngredientFormatter(
            self.config.formatter.format_ingredient,
            unit_formatter=self.unit_formatter,
            pantry_list=PantryList(
                self.config.pantry_list,
                gsheets_helper=GsheetsHelper(self.config.api.gsheets),
            ),
        )
        return IngredientField(
            config=self.config.formatter.get_ingredient_field,
            ingredient_formatter=ingredient_formatter,
            recipe_book=RecipeBook(self.config.recipe_book),
        )

    def _set_primary_shopping_date(self) -> date:
        default_date = self.due_date_formatter.get_date_relative_to_anchor(
            self.config.grocery_list.shopping.primary_day
        ).date()

        if default_date >= self.due_date_formatter.get_anchor_date():
            return default_date - timedelta(days=7)

        return default_date

    def _set_secondary_shopping_info(self) -> None:
        self.secondary_shopping_date = (
            self.due_date_formatter.get_date_relative_to_anchor(
                self.config.grocery_list.shopping.secondary_day
            ).date()
        )
        self.second_shopping_day_group = (
            self.config.grocery_list.shopping.secondary_group
        )

    def extract_ingredients_from_menu(self) -> pd.DataFrame:
        # menu = Menu(config=config)
        # delete get_menu_for_grocery_list, related class, function, & tests
        # menu.load_final_menu(gsheets_helper: GsheetsHelper)
        # use new class, i.e. GroceryListMenuProcessor
        # and its function, i.e. extract_ingredients_from_menu
        # --- first add manual ingredients to dataframe (other class function)
        # --- would first process recipes in another function call
        # ------ given a recipe, parse & process all its sub(n)-recipes in a
        # ------ function-bound FIFO queue. To avoid infinite recursions, each
        # ------ sub-recipe should have a depth number that gets set when it's
        # ------ added into the function-bound queue (current_depth+1). We'd
        # ------ have a config value where we set the max. depth (i.e. 3). The
        # ------ goal isn't just to prevent infinite recursion but also the
        # ------ complexity of our recipes. If it's exceeded, we toss a custom
        # ------ error for that recipe that will be added to the exception
        # ------ handler so other recipes can be continued. add ingredients to
        # ------ dataframe. with each evaluation of a sub-recipe, we are asked
        # ------ about preparing this, for simplicity, basically like
        # ------ _add_referenced_recipe_to_queue but cleaner ---would be nice
        # ------ if modeled similar to _process_menu_recipe's usage
        # ------ in _fill_menu_template
        # ------ (later step) keep track of already called sub-recipes to
        # ------ reduce re-asking questions & keep track of total amount needed
        # --- later concatenate/process ingredients
        # --- outputs a non-aggregated dataframe -> just ingredients, dates
        # --- outputs a prep list that would go to todoist (this should
        # --- NOT have task formatting -> instead do in todoist function
        # send prep list to todoist, if exists & in prod mode
        #
        #
        # --- functions (not exhaustive) now obsolete and to be removed from old
        # --- & their tests moved to the new functions
        # ---- _add_menu_recipe_to_queue
        # ---- _add_bulk_manual_ingredient_to_grocery_list
        # ---- _process_recipe_queue

        menu = Menu(config=self.config)
        (
            menu_ingredient_list,
            menu_recipe_list,
        ) = menu.get_menu_for_grocery_list()

        grocery_list = GroceryListOld(
            self.config.grocery_list,
            due_date_formatter=self.due_date_formatter,
            ingredient_field=self._get_ingredient_field(),
            unit_formatter=self.unit_formatter,
        )
        return grocery_list.extract_ingredients_from_menu(
            menu_ingredient_list, menu_recipe_list
        )

    def prepare_grocery_list(
        self, raw_grocery_df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        # use the output from extract_ingredients_from_menu
        # use new class, i.e. GroceryListAggregator
        # and its function, aggregate_ingredients
        # --- this function will call on functions contained in its class
        # --- that are in _aggregate_grocery_list
        # --- outputs an aggregrated grocery list in a dataframe

        # send aggregated grocery list to todoist, if prod mode
        # todoist class does formatting of strings

        grocery_list = GroceryListOld(
            self.config.grocery_list,
            due_date_formatter=self.due_date_formatter,
            ingredient_field=self._get_ingredient_field(),
            unit_formatter=self.unit_formatter,
        )

        return grocery_list.prepare_grocery_list(raw_grocery_df=raw_grocery_df)

    def export_to_todoist(
        self, grocery_list_df: pd.DataFrame, prep_task_df: pd.DataFrame
    ) -> None:
        # switch to class specific to todoist output
        todoist_helper = TodoistHelper(self.config.api.todoist)

        grocery_list = GroceryListOld(
            self.config.grocery_list,
            due_date_formatter=self.due_date_formatter,
            ingredient_field=self._get_ingredient_field(),
            unit_formatter=self.unit_formatter,
        )

        grocery_list.upload_grocery_list_to_todoist(
            todoist_helper=todoist_helper,
            grocery_list_df=grocery_list_df,
        )
        grocery_list.send_preparation_to_todoist(
            todoist_helper=todoist_helper, prep_task_df=prep_task_df
        )
