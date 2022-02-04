import hydra
from omegaconf import DictConfig
from sous_chef.formatter.format_unit import UnitFormatter
from sous_chef.formatter.ingredient.format_ingredient import IngredientFormatter
from sous_chef.formatter.ingredient.format_ingredient_field import (
    IngredientFieldFormatter,
)
from sous_chef.grocery_list.generate_grocery_list import GroceryList
from sous_chef.menu.create_menu import Menu
from sous_chef.messaging.gsheets_api import GsheetsHelper
from sous_chef.messaging.todoist_api import TodoistHelper
from sous_chef.pantry_list.read_pantry_list import PantryList
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from sous_chef.rtk.read_write_rtk import RtkService
from structlog import get_logger

LOG = get_logger()


@hydra.main(config_path="../config", config_name="grocery_list")
def main(config: DictConfig) -> None:
    if config.grocery_list.run_mode.only_clean_todoist_mode:
        # TODO all should be contained in todoist helper method & executed here
        todoist_helper = TodoistHelper(config.messaging.todoist)
        print(
            "Deleting previous tasks in project {}".format(
                config.grocery_list.todoist_project_name
            )
        )
        [
            todoist_helper.delete_all_items_in_project(
                config.grocery_list.todoist_project_name
            )
            for _ in range(3)
        ]
    else:
        # unzip latest recipe versions
        rtk_service = RtkService(config.rtk)
        rtk_service.unzip()

        recipe_book = RecipeBook(config.recipe_book)
        ingredient_formatter = _get_ingredient_formatter(config)
        ingredient_field_formatter = IngredientFieldFormatter(
            config.formatter.format_ingredient_field,
            ingredient_formatter=ingredient_formatter,
            recipe_book=recipe_book,
        )

        # get menu for grocery list
        menu = Menu(
            config.menu,
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
            ingredient_field_formatter=ingredient_field_formatter,
        )
        grocery_list.get_grocery_list_from_menu(
            menu_ingredient_list, menu_recipe_list
        )

        # send grocery list to desired output
        # TODO add functionality to choose which helper/function
        if config.grocery_list.run_mode.with_todoist:
            todoist_helper = TodoistHelper(config.messaging.todoist)
            grocery_list.upload_grocery_list_to_todoist(todoist_helper)
            grocery_list.send_bean_preparation_to_todoist(todoist_helper)


def _get_ingredient_formatter(config: DictConfig):
    gsheets_helper = GsheetsHelper(config.messaging.gsheets)
    pantry_list = PantryList(config.pantry_list, gsheets_helper=gsheets_helper)
    unit_formatter = UnitFormatter(config.formatter.format_unit)
    return IngredientFormatter(
        config.formatter.format_ingredient,
        unit_formatter=unit_formatter,
        pantry_list=pantry_list,
    )


if __name__ == "__main__":
    main()
