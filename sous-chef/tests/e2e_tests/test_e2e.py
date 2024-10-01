from unittest.mock import PropertyMock, patch

import pandas as pd
import pytest
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.grocery_list.main import run_grocery_list
from sous_chef.menu.main import run_menu
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from tests.data.util_data import (
    get_final_grocery_list,
    get_final_menu,
    get_menu_history,
    get_tasks_grocery_list,
    get_tasks_menu,
)
from tests.e2e_tests.util import PROJECT, Base

from utilities.testing.pandas_util import assert_equal_dataframe


@pytest.mark.gsheets
@pytest.mark.todoist
class Test(Base):
    @staticmethod
    @pytest.fixture(autouse=True)
    def run_before_and_after_tests(todoist_helper):
        """Fixture to execute asserts before and after a test is run"""
        todoist_helper.delete_all_items_in_project(project=PROJECT)

        yield  # this is where the testing happens

        # Teardown : fill with any logic you want
        todoist_helper.delete_all_items_in_project(project=PROJECT)

    @staticmethod
    def _convert_task_list_to_df(todoist_helper):
        project_id = todoist_helper.get_project_id(PROJECT)
        task_list = todoist_helper.connection.get_tasks(project_id=project_id)
        task_df = pd.DataFrame.from_records(
            [task.__dict__ for task in task_list]
        )
        task_df.due = task_df.due.astype(str)
        return (
            task_df[["content", "due", "labels", "priority"]]
            .sort_values("content")
            .reset_index(drop=True)
        )

    def _run_menu(self):
        config = self._get_config("menu_main")
        self._set_config_menu(config)
        config.menu.record_menu_history.save_loc.worksheet = "tmp-menu-history"

        with patch.object(
            RecipeBook,
            "dataframe",
            new_callable=PropertyMock,
            return_value=self._get_local_recipe_book(config.recipe_book),
        ):
            config.menu.create_menu.input_method = "fixed"
            run_menu(config)

            config.menu.create_menu.input_method = "final"
            return run_menu(config)

    def _run_grocery_list(self):
        config = self._get_config("grocery_list")
        self._set_config_menu(config)
        config.grocery_list.preparation.project_name = PROJECT
        config.grocery_list.todoist.project_name = PROJECT
        config.grocery_list.run_mode.with_todoist = True
        config.grocery_list.run_mode.check_referenced_recipe = False
        with patch.object(
            RecipeBook,
            "dataframe",
            new_callable=PropertyMock,
            return_value=self._get_local_recipe_book(config.recipe_book),
        ):
            return run_grocery_list(config)

    # TODO modify so that uses rtk & opened recipe json
    @patch("sous_chef.rtk.read_write_rtk.RtkService.unzip")
    def test_e2e(
        self,
        patch_rtk_service,
        frozen_due_datetime_formatter,
        menu_history,
        todoist_helper,
    ):
        with patch.object(
            DueDatetimeFormatter,
            "anchor_datetime",
            new_callable=PropertyMock,
            return_value=frozen_due_datetime_formatter.anchor_datetime,
        ):
            with patch.object(RecipeBook, "__post_init__", return_value=None):
                final_menu = self._run_menu()
                assert_equal_dataframe(final_menu, get_final_menu())

                menu_history._load_history()
                assert_equal_dataframe(
                    menu_history.dataframe, get_menu_history()
                )

                tasks_menu = self._convert_task_list_to_df(
                    todoist_helper=todoist_helper
                )
                assert_equal_dataframe(tasks_menu, get_tasks_menu())

                final_grocery_list = self._run_grocery_list()
                assert_equal_dataframe(
                    final_grocery_list, get_final_grocery_list()
                )

                tasks_grocery_list = self._convert_task_list_to_df(
                    todoist_helper=todoist_helper
                )
                assert_equal_dataframe(
                    tasks_grocery_list, get_tasks_grocery_list()
                )
