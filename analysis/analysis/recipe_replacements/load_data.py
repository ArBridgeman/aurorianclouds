from datetime import timedelta

from hydra import compose, initialize
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.menu.create_menu._from_fixed_template import FixedTemplates
from sous_chef.menu.create_menu.create_menu import Menu
from sous_chef.menu.main import _get_ingredient_formatter
from sous_chef.menu.record_menu_history import MenuHistorian
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from sous_chef.rtk.read_write_rtk import RtkService

from utilities.api.gsheets_api import GsheetsHelper

# from structlog import get_logger


def update_data():
    with initialize(
        version_base=None, config_path="../../../sous-chef/config/"
    ):
        config = compose(config_name="menu_main")
        rtk_service = RtkService(config.rtk)
        rtk_service.unzip()


def get_recipe_book():
    with initialize(
        version_base=None, config_path="../../../sous-chef/config/"
    ):
        config = compose(config_name="menu_main")
        return RecipeBook(config.recipe_book)


def get_menu_historian():
    with initialize(
        version_base=None, config_path="../../../sous-chef/config/"
    ):
        config = compose(config_name="menu_main")
        gsheets_helper = GsheetsHelper(config.api.gsheets)
        due_date_formatter = DueDatetimeFormatter(config=config.date.due_date)

        menu_historian = MenuHistorian(
            config=config.menu.record_menu_history,
            current_menu_start_date=due_date_formatter.get_anchor_datetime()
            + timedelta(days=1),
            gsheets_helper=gsheets_helper,
        )

        return menu_historian


def create_menu(recipe_book: RecipeBook, menu_historian: MenuHistorian) -> Menu:
    with initialize(
        version_base=None, config_path="../../../sous-chef/config/"
    ):
        config = compose(config_name="menu_main")

        gsheets_helper = GsheetsHelper(config.api.gsheets)
        due_date_formatter = DueDatetimeFormatter(config=config.date.due_date)
        ingredient_formatter = _get_ingredient_formatter(config, gsheets_helper)

        menu = Menu(
            config=config.menu.create_menu,
            due_date_formatter=due_date_formatter,
            gsheets_helper=gsheets_helper,
            ingredient_formatter=ingredient_formatter,
            menu_historian=menu_historian,
            recipe_book=recipe_book,
        )
    return menu


def get_menu_history_uuids(menu_historian: MenuHistorian):
    with initialize(
        version_base=None, config_path="../../../sous-chef/config/"
    ):
        config = compose(config_name="menu_main")

        history = menu_historian.get_history_from(
            days_ago=config.menu.create_menu.menu_history_recent_days
        )

        return list(history.uuid.values)


def get_future_menu_uuids(menu: Menu, future_menus: int = None):

    fixed_templates = FixedTemplates(
        config=menu.config.fixed,
        due_date_formatter=menu.due_date_formatter,
        gsheets_helper=menu.gsheets_helper,
    )

    future_uuid_tuple = menu._get_future_menu_uuids(
        future_menus=fixed_templates.select_upcoming_menus(
            num_weeks_in_future=future_menus
            if future_menus
            else menu.config.fixed.already_in_future_menus.num_weeks  # noqa: E501
        )
    )

    return future_uuid_tuple
