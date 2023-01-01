from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from hydra import compose, initialize
from omegaconf import DictConfig
from requests.exceptions import HTTPError
from sous_chef.recipe_book.read_recipe_book import RecipeBook


def clean_up_add_todoist_task(todoist_helper, task_id: str):
    # delete task
    todoist_helper.connection.delete_task(task_id=task_id)

    # verify task was deleted
    with pytest.raises(HTTPError) as error:
        todoist_helper.connection.get_task(task_id=task_id)
    assert str(error.value) == (
        "404 Client Error: Not Found for url: "
        f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    )


def get_location():
    return Path(__file__).parent.absolute()


class BaseMain:
    @staticmethod
    def _get_config(config_name: str):
        with initialize(version_base=None, config_path="../../config"):
            return compose(config_name=config_name)

    @staticmethod
    def _get_local_recipe_book(config: DictConfig):
        with patch.object(RecipeBook, "__post_init__", lambda x: None):
            recipe_book = RecipeBook(config)
            recipe_book.recipe_book_path = get_location() / "data"
            recipe_book._read_recipe_book()
            return recipe_book.dataframe

    @staticmethod
    def _set_config_menu(config: DictConfig):
        create_menu = config.menu.create_menu
        create_menu.final_menu.worksheet = "test-tmp-menu"
        create_menu.fixed.basic = "test-menu-basic"
        create_menu.fixed.file_prefix = "test-menu-"
        create_menu.fixed.menu_number = 0

    @staticmethod
    def _set_config_run_mode(config: DictConfig):
        if "only_clean_todoist" in config.run_mode.keys():
            config.run_mode.only_clean_todoist_mode = False
        if "with_gmail" in config.run_mode.keys():
            config.run_mode.with_gmail = False
        config.run_mode.with_todoist = False


def get_final_menu() -> pd.DataFrame:
    final_menu = pd.read_csv(
        get_location() / "data/final_menu.csv",
        dtype={"uuid": str},
        header=0,
    )
    final_menu.eat_unit.fillna("", inplace=True)
    final_menu.uuid.fillna("NaN", inplace=True)
    final_menu.cook_datetime = pd.to_datetime(final_menu.cook_datetime)
    final_menu.prep_datetime = pd.to_datetime(final_menu.prep_datetime)
    final_menu.time_total = pd.to_timedelta(final_menu.time_total)
    return final_menu
