from unittest.mock import PropertyMock, patch

import pandas as pd
from hydra import compose, initialize
from omegaconf import DictConfig
from sous_chef.grocery_list.main import run_grocery_list
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from sous_chef.rtk.read_write_rtk import RtkService
from tests.integration_tests.util import get_location
from tests.util import assert_equal_dataframe


class TestMain:
    @staticmethod
    def _get_local_recipe_book(config: DictConfig):
        with patch.object(RecipeBook, "__post_init__", lambda x: None):
            recipe_book = RecipeBook(config)
            recipe_book.recipe_book_path = get_location() / "data"
            recipe_book._read_recipe_book()
            return recipe_book.dataframe

    def test_run_grocery_list_without_todoist(self):
        with initialize(version_base=None, config_path="../../../config"):
            config = compose(config_name="grocery_list")
            config.grocery_list.run_mode.only_clean_todoist_mode = False
            config.grocery_list.run_mode.with_todoist = False
            config.menu.create_menu.final_menu.worksheet = "test-tmp-menu"
            config.menu.create_menu.fixed.basic = "test-menu-basic"
            config.menu.create_menu.fixed.file_prefix = "test-menu-"
            with patch.object(RtkService, "unzip", lambda x: None):
                with patch.object(RecipeBook, "__post_init__", lambda x: None):
                    with patch.object(
                        RecipeBook,
                        "dataframe",
                        new_callable=PropertyMock,
                        return_value=self._get_local_recipe_book(
                            config.recipe_book
                        ),
                    ):
                        final_grocery_list = run_grocery_list(config)

                        expected_result = pd.read_csv(
                            get_location() / "data/final_grocery_list.csv",
                            dtype={"barcode": str},
                            header=0,
                        )
                        expected_result.barcode.fillna("", inplace=True)
                        expected_result.from_recipe = (
                            expected_result.from_recipe.apply(
                                lambda cell: cell[1:-1].split(", ")
                            )
                        )
                        expected_result.for_day_str = (
                            expected_result.for_day_str.apply(
                                lambda cell: cell[1:-1].split(", ")
                            )
                        )
                        expected_result.for_day = pd.to_datetime(
                            expected_result.for_day
                        )
                        assert_equal_dataframe(
                            final_grocery_list, expected_result
                        )
