import datetime
from unittest.mock import patch

import pandas as pd
import pytest
from freezegun import freeze_time
from sous_chef.grocery_list.generate_grocery_list.generate_grocery_list import (
    GroceryListOld,
)
from tests.conftest import FROZEN_DATE

from utilities.validate_choice import YesNoChoices


@pytest.fixture
@freeze_time(FROZEN_DATE)
def grocery_list(
    fixed_grocery_config,
    unit_formatter,
    mock_ingredient_field,
    frozen_due_datetime_formatter,
):
    grocery_list = GroceryListOld(
        config=fixed_grocery_config.grocery_list,
        due_date_formatter=frozen_due_datetime_formatter,
        unit_formatter=unit_formatter,
        ingredient_field=mock_ingredient_field,
    )
    grocery_list.second_shopping_day_group = ["vegetables"]
    return grocery_list


class TestGroceryList:
    @staticmethod
    @pytest.mark.todoist
    def test__send_preparation_to_todoist(
        frozen_due_datetime_formatter,
        fixed_grocery_config,
        grocery_list,
        todoist_helper,
    ):
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
