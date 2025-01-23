from datetime import datetime, timedelta
from pathlib import Path

import hydra
import numpy as np
from omegaconf import DictConfig
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.formatter.format_unit import UnitFormatter
from sous_chef.formatter.ingredient.format_ingredient import IngredientFormatter
from sous_chef.menu.create_menu.create_menu import Menu
from sous_chef.menu.record_menu_history import MenuHistorian
from sous_chef.pantry_list.read_pantry_list import PantryList
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from sous_chef.rtk.read_write_rtk import RtkService
from structlog import get_logger

from utilities.api.gsheets_api import GsheetsHelper

ABS_FILE_PATH = Path(__file__).absolute().parent
FILE_LOGGER = get_logger(__name__)


def run_menu(config: DictConfig):
    # unzip latest recipe versions
    rtk_service = RtkService(config.rtk)
    rtk_service.unzip()

    gsheets_helper = GsheetsHelper(config.api.gsheets)
    ingredient_formatter = _get_ingredient_formatter(config, gsheets_helper)

    due_date_formatter = DueDatetimeFormatter(config=config.date.due_date)

    menu_historian = MenuHistorian(
        config=config.menu.record_menu_history,
        current_menu_start_date=due_date_formatter.get_anchor_datetime()
        + timedelta(days=1),
        gsheets_helper=gsheets_helper,
    )

    recipe_book = RecipeBook(config.recipe_book)

    menu = Menu(
        config=config,
        menu_config=config.menu.create_menu,
        due_date_formatter=due_date_formatter,
        gsheets_helper=gsheets_helper,
        ingredient_formatter=ingredient_formatter,
        menu_historian=menu_historian,
        recipe_book=recipe_book,
    )
    if config.menu.create_menu.input_method == "fixed":
        return menu.fill_menu_template()
    elif config.menu.create_menu.input_method == "final":
        return menu.finalize_menu_to_external_services(
            config_todoist=config.api.todoist
        )


@hydra.main(
    config_path="../../config/", config_name="menu_main", version_base=None
)
def main(config: DictConfig):
    if config.random.seed is None:
        config.random.seed = datetime.now().timestamp()
    config.random.seed = int(config.random.seed)
    # globally set random seed for numpy based calls
    np.random.seed(config.random.seed)

    try:
        run_menu(config)
    except Exception as e:
        raise e
    finally:
        FILE_LOGGER.info(
            f"Use random seed {config.random.seed} to reproduce this run!"
        )


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
