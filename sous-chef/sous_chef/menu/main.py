from datetime import timedelta

import hydra
from omegaconf import DictConfig
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.formatter.format_unit import UnitFormatter
from sous_chef.formatter.ingredient.format_ingredient import IngredientFormatter
from sous_chef.menu.create_menu import Menu
from sous_chef.menu.record_menu_history import MenuHistorian
from sous_chef.messaging.gmail_api import GmailHelper
from sous_chef.messaging.gsheets_api import GsheetsHelper
from sous_chef.messaging.todoist_api import TodoistHelper
from sous_chef.pantry_list.read_pantry_list import PantryList
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from sous_chef.rtk.read_write_rtk import RtkService


def run_menu(config: DictConfig):
    # unzip latest recipe versions
    rtk_service = RtkService(config.rtk)
    rtk_service.unzip()

    gsheets_helper = GsheetsHelper(config.messaging.gsheets)
    ingredient_formatter = _get_ingredient_formatter(config, gsheets_helper)

    due_date_formatter = DueDatetimeFormatter(
        anchor_day=config.date.due_date.anchor_day
    )

    menu_historian = MenuHistorian(
        config=config.menu.record_menu_history,
        current_menu_start_date=due_date_formatter.anchor_datetime
        + timedelta(days=1),
        gsheets_helper=gsheets_helper,
    )

    recipe_book = RecipeBook(config.recipe_book)

    # TODO move manual method here
    menu = Menu(
        config=config.menu.create_menu,
        due_date_formatter=due_date_formatter,
        gsheets_helper=gsheets_helper,
        ingredient_formatter=ingredient_formatter,
        menu_historian=menu_historian,
        recipe_book=recipe_book,
    )
    if config.menu.create_menu.input_method == "fixed":
        menu.finalize_fixed_menu()
    elif config.menu.create_menu.input_method == "final":
        final_menu = menu.load_final_menu()
        menu.save_with_menu_historian()

        if config.menu.run_mode.with_todoist:
            todoist_helper = TodoistHelper(config.messaging.todoist)
            menu.upload_menu_to_todoist(todoist_helper)

        if config.menu.run_mode.with_gmail:
            gmail_helper = GmailHelper(config.messaging.gmail)
            menu.send_menu_to_gmail(gmail_helper)

        return final_menu


@hydra.main(config_path="../../config/", config_name="menu_main")
def main(config: DictConfig):
    run_menu(config)


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
