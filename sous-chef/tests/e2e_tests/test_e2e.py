from unittest.mock import PropertyMock, patch

import pandas as pd
import pytest
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.grocery_list.main import run_grocery_list
from sous_chef.menu.main import run_menu
from tests.e2e_tests.conftest import PROJECT

from utilities.testing.pandas_util import assert_equal_dataframe
from utilities.validate_choice import YesNoChoices


@pytest.mark.gsheets
@pytest.mark.todoist
class Test:
    @staticmethod
    @pytest.fixture(autouse=True)
    def run_before_and_after_tests(todoist_helper):
        with patch("builtins.input", side_effect=[YesNoChoices.yes.value]):
            todoist_helper.delete_all_items_in_project(project=PROJECT)

        yield

        with patch("builtins.input", side_effect=[YesNoChoices.yes.value]):
            todoist_helper.delete_all_items_in_project(project=PROJECT)

    @staticmethod
    def _convert_task_list_to_df(todoist_helper):
        project_id = todoist_helper.get_project_id(PROJECT)
        task_list = todoist_helper._get_tasks(project_id=project_id)
        task_df = pd.DataFrame.from_records(
            [task.__dict__ for task in task_list]
        )
        task_df.due = task_df.due.astype(str).str.replace(
            r"\s+", "", regex=True
        )
        return (
            task_df[["content", "due", "labels", "priority"]]
            .sort_values("content")
            .reset_index(drop=True)
        )

    # TODO modify so that uses rtk & opened recipe json
    @patch("sous_chef.rtk.read_write_rtk.RtkService.unzip")
    def test_e2e(
        self,
        patch_rtk_service,
        frozen_due_datetime_formatter,
        grocery_config,
        menu_history,
        menu_config,
        todoist_helper,
        fixed_final_menu,
        fixed_menu_history,
        tasks_menu,
        final_grocery_list,
        tasks_grocery_list,
    ):
        # fill menu template & finalization
        with patch.object(
            DueDatetimeFormatter,
            "anchor_datetime",
            new_callable=PropertyMock,
            return_value=frozen_due_datetime_formatter.anchor_datetime,
        ):
            menu_config.menu.create_menu.input_method = "fixed"
            run_menu(menu_config)

            menu_config.menu.create_menu.input_method = "final"
            final_menu = run_menu(menu_config)
        assert_equal_dataframe(final_menu, fixed_final_menu)

        menu_history._load_history()
        assert_equal_dataframe(menu_history.dataframe, fixed_menu_history)

        tasks_menu_result = self._convert_task_list_to_df(
            todoist_helper=todoist_helper
        )
        assert_equal_dataframe(tasks_menu_result, tasks_menu)

        # create grocery list
        with patch.object(
            DueDatetimeFormatter,
            "anchor_datetime",
            new_callable=PropertyMock,
            return_value=frozen_due_datetime_formatter.anchor_datetime,
        ):
            with patch("builtins.input", side_effect=[YesNoChoices.yes.value]):
                final_grocery_list_result = run_grocery_list(grocery_config)
        final_grocery_list_result.pint_unit = (
            final_grocery_list_result.pint_unit.apply(lambda x: str(x))
        )
        assert_equal_dataframe(final_grocery_list_result, final_grocery_list)

        tasks_grocery_list_result = self._convert_task_list_to_df(
            todoist_helper=todoist_helper
        )
        assert_equal_dataframe(tasks_grocery_list_result, tasks_grocery_list)
