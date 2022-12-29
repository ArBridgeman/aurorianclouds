from unittest.mock import PropertyMock, patch

import pandas as pd
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.menu.main import run_menu
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from sous_chef.rtk.read_write_rtk import RtkService
from tests.integration_tests.util import BaseMain, get_location
from tests.util import assert_equal_dataframe


class TestMain(BaseMain):
    def test_run_menu_without_todoist(self, frozen_due_datetime_formatter):
        config = self._get_config("menu_main")
        self._set_config_menu(config)
        self._set_config_run_mode(config.menu)
        config.menu.run_mode.with_todoist = False
        config.menu.run_mode.with_gmail = False

        config.menu.record_menu_history.save_loc.worksheet = "tmp-menu-history"

        anchor_date = frozen_due_datetime_formatter.anchor_datetime
        # TODO modify so that uses rtk & opened recipe json
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
                    with patch.object(
                        DueDatetimeFormatter, "__post_init__", lambda x: None
                    ):
                        with patch.object(
                            DueDatetimeFormatter,
                            "anchor_datetime",
                            new_callable=PropertyMock,
                            return_value=anchor_date,
                        ):
                            config.menu.create_menu.input_method = "fixed"
                            run_menu(config)

                            config.menu.create_menu.input_method = "final"
                            final_menu = run_menu(config)

        expected_result = pd.read_csv(
            get_location() / "data/final_menu.csv",
            dtype={"uuid": str},
            header=0,
        )
        expected_result.eat_unit.fillna("", inplace=True)
        expected_result.uuid.fillna("NaN", inplace=True)
        expected_result.cook_datetime = pd.to_datetime(
            expected_result.cook_datetime
        )
        expected_result.prep_datetime = pd.to_datetime(
            expected_result.prep_datetime
        )
        expected_result.time_total = pd.to_timedelta(expected_result.time_total)
        assert_equal_dataframe(final_menu, expected_result)