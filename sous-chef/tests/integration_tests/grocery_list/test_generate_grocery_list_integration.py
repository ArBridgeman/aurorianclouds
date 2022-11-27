import pandas as pd
import pytest


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

        weekday = "Monday"
        hour = 17
        minute = 30
        prep_task_df = pd.DataFrame(
            {
                "task": ["test task"],
                "weekday": [weekday],
                "hour": [hour],
                "minute": [minute],
                "from_recipe": [["test recipe"]],
                "for_day_str": [["Tuesday"]],
            }
        )
        grocery_list.queue_preparation = prep_task_df
        grocery_list.send_preparation_to_todoist(todoist_helper)
