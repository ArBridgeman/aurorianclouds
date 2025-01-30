from dataclasses import dataclass
from datetime import date, timedelta

from omegaconf import DictConfig
from sous_chef.date.get_due_date import DueDatetimeFormatter


@dataclass
class GroceryList:
    def __init__(
        self, config: DictConfig, due_date_formatter: DueDatetimeFormatter
    ):
        self.config = config
        self.due_date_formatter = due_date_formatter

        self.primary_shopping_date = self._set_primary_shopping_date()

        self.secondary_shopping_date = None
        self.second_shopping_day_group = ()
        if self.config.shopping.secondary_day:
            self._set_secondary_shopping_info()

        calendar_week = self.due_date_formatter.get_calendar_week()
        self.app_week_label = f"app-week-{calendar_week}"

    def _set_primary_shopping_date(self) -> date:
        default_date = self.due_date_formatter.get_date_relative_to_anchor(
            self.config.shopping.primary_day
        ).date()

        if default_date >= self.due_date_formatter.get_anchor_date():
            return default_date - timedelta(days=7)

        return default_date

    def _set_secondary_shopping_info(self) -> None:
        self.secondary_shopping_date = (
            self.due_date_formatter.get_date_relative_to_anchor(
                self.config.shopping.secondary_day
            ).date()
        )
        self.second_shopping_day_group = self.config.shopping.secondary_group

    def extract_ingredients_from_menu(self):
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
        pass

    def prepare_grocery_list(self):
        # use the output from extract_ingredients_from_menu
        # use new class, i.e. GroceryListAggregator
        # and its function, aggregate_ingredients
        # --- this function will call on functions contained in its class
        # --- that are in _aggregate_grocery_list
        # --- outputs an aggregrated grocery list in a dataframe

        # send aggregated grocery list to todoist, if prod mode
        # todoist class does formatting of strings
        pass
