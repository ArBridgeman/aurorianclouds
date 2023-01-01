from unittest.mock import PropertyMock, patch

import pandas as pd
import pytest
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.grocery_list.main import run_grocery_list
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from sous_chef.rtk.read_write_rtk import RtkService
from tests.integration_tests.util import BaseMain, get_location
from tests.util import assert_equal_dataframe


@pytest.mark.gsheets
class TestMain(BaseMain):
    # dependent on tmp-menu being run before
    def test_run_grocery_list_without_todoist(
        self, frozen_due_datetime_formatter
    ):
        config = self._get_config("grocery_list")
        self._set_config_run_mode(config.grocery_list)
        self._set_config_menu(config)
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
                            final_grocery_list = run_grocery_list(config)

        expected_result = pd.read_csv(
            get_location() / "data/final_grocery_list.csv",
            dtype={"barcode": str},
            header=0,
        )
        expected_result.barcode.fillna("", inplace=True)
        expected_result.from_recipe = expected_result.from_recipe.apply(
            lambda cell: cell[1:-1].split(", ")
        )
        expected_result.for_day_str = expected_result.for_day_str.apply(
            lambda cell: cell[1:-1].split(", ")
        )
        expected_result.for_day = pd.to_datetime(expected_result.for_day)
        assert_equal_dataframe(final_grocery_list, expected_result)
