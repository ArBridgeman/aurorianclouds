import hydra
import pandas as pd
from omegaconf import DictConfig
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.formatter.format_unit import UnitFormatter
from sous_chef.formatter.ingredient.format_ingredient import IngredientFormatter
from sous_chef.formatter.ingredient.get_ingredient_field import IngredientField
from sous_chef.grocery_list.generate_grocery_list import GroceryList
from sous_chef.menu.create_menu.create_menu import Menu
from sous_chef.pantry_list.read_pantry_list import PantryList
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from sous_chef.rtk.read_write_rtk import RtkService
from structlog import get_logger

from utilities.api.gsheets_api import GsheetsHelper
from utilities.api.todoist_api import TodoistHelper

LOGGER = get_logger(__name__)


def run_grocery_list(config: DictConfig) -> pd.DataFrame:
    if config.grocery_list.run_mode.only_clean_todoist_mode:
        todoist_helper = TodoistHelper(config.api.todoist)
        LOGGER.info(
            "Deleting previous tasks in project {}".format(
                config.grocery_list.todoist.project_name
            )
        )
        todoist_helper.delete_all_items_in_project(
            config.grocery_list.todoist.project_name
        )
    else:
        # unzip latest recipe versions
        rtk_service = RtkService(config.rtk)
        rtk_service.unzip()

        gsheets_helper = GsheetsHelper(config.api.gsheets)
        unit_formatter = UnitFormatter()
        recipe_book = RecipeBook(config.recipe_book)
        ingredient_formatter = _get_ingredient_formatter(
            config, gsheets_helper, unit_formatter
        )
        ingredient_field = IngredientField(
            config.formatter.get_ingredient_field,
            ingredient_formatter=ingredient_formatter,
            recipe_book=recipe_book,
        )

        due_date_formatter = DueDatetimeFormatter(config=config.date.due_date)

        # get menu for grocery list
        menu = Menu(
            config=config.menu.create_menu,
            due_date_formatter=due_date_formatter,
            gsheets_helper=gsheets_helper,
            ingredient_formatter=ingredient_formatter,
            recipe_book=recipe_book,
        )
        (
            menu_ingredient_list,
            menu_recipe_list,
        ) = menu.get_menu_for_grocery_list()

        # get grocery list
        grocery_list = GroceryList(
            config.grocery_list,
            due_date_formatter=due_date_formatter,
            ingredient_field=ingredient_field,
            unit_formatter=unit_formatter,
        )
        final_grocery_list = grocery_list.get_grocery_list_from_menu(
            menu_ingredient_list, menu_recipe_list
        )

        # send grocery list to desired output
        # TODO add functionality to choose which helper/function
        if config.grocery_list.run_mode.with_todoist:
            todoist_helper = TodoistHelper(config.api.todoist)
            grocery_list.upload_grocery_list_to_todoist(todoist_helper)
            grocery_list.send_preparation_to_todoist(todoist_helper)
        return final_grocery_list


@hydra.main(
    config_path="../../config", config_name="grocery_list", version_base=None
)
def main(config: DictConfig) -> None:
    run_grocery_list(config=config)


def _get_ingredient_formatter(
    config: DictConfig,
    gsheets_helper: GsheetsHelper,
    unit_formatter: UnitFormatter,
):
    pantry_list = PantryList(config.pantry_list, gsheets_helper=gsheets_helper)
    return IngredientFormatter(
        config.formatter.format_ingredient,
        unit_formatter=unit_formatter,
        pantry_list=pantry_list,
    )


if __name__ == "__main__":
    main()
