import hydra
from omegaconf import DictConfig
from sous_chef.formatter.format_unit import UnitFormatter
from sous_chef.formatter.ingredient.format_ingredient import IngredientFormatter
from sous_chef.menu.create_menu import Menu
from sous_chef.messaging.gsheets_api import GsheetsHelper
from sous_chef.messaging.todoist_api import TodoistHelper
from sous_chef.pantry_list.read_pantry_list import PantryList
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from sous_chef.rtk.read_write_rtk import RtkService


@hydra.main(config_path="../../config", config_name="menu")
def main(config: DictConfig):
    # unzip latest recipe versions
    rtk_service = RtkService(config.rtk)
    rtk_service.unzip()

    gsheets_helper = GsheetsHelper(config.messaging.gsheets)
    ingredient_formatter = _get_ingredient_formatter(config, gsheets_helper)
    recipe_book = RecipeBook(config.recipe_book)

    # TODO move manual method here
    menu = Menu(
        config.menu,
        ingredient_formatter=ingredient_formatter,
        recipe_book=recipe_book,
    )
    if config.menu.input_method == "fixed":
        menu.finalize_fixed_menu(gsheets_helper)

    if config.menu.run_mode.with_todoist:
        todoist_helper = TodoistHelper(config.messaging.todoist)
        menu.upload_menu_to_todoist(todoist_helper)


def _get_ingredient_formatter(
    config: DictConfig, gsheets_helper: GsheetsHelper
):
    pantry_list = PantryList(config.pantry_list, gsheets_helper=gsheets_helper)
    return IngredientFormatter(
        config.formatter.format_ingredient,
        unit_formatter=UnitFormatter(),
        pantry_list=pantry_list,
    )


if __name__ == "__main__":
    main()
