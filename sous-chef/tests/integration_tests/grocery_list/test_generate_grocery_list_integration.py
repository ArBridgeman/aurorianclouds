import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from utilities.validate_choice import YesNoChoices


class TestGroceryList:
    @staticmethod
    @pytest.mark.todoist
    def test__send_preparation_to_todoist(
        frozen_due_datetime_formatter,
        config_grocery_list,
        grocery_list,
        todoist_helper,
    ):
        config_grocery_list.preparation.project_name = "Pytest-area"
        config_grocery_list.todoist.remove_existing_prep_task = True

        prep_task_df = pd.DataFrame(
            {
                "task": ["test task"],
                "from_recipe": [["test recipe"]],
                "for_day_str": [["Tuesday"]],
                "due_date": datetime.datetime(
                    year=2022, month=1, day=24, hour=17, minute=30
                ),
            }
        )
        grocery_list.queue_preparation = prep_task_df

        with patch("builtins.input", side_effect=[YesNoChoices.yes.value]):
            grocery_list.send_preparation_to_todoist(todoist_helper)
