import pandas as pd
import pytest
from freezegun import freeze_time
from sous_chef.menu.create_menu._export_to_todoist import MenuForTodoist
from tests.conftest import FROZEN_DATE


@pytest.fixture
@freeze_time(FROZEN_DATE)
def menu_for_todoist(
    menu_config,
    frozen_due_datetime_formatter,
    mock_all_menus_df,
    mock_todoist_helper,
):
    mock_todoist_helper.get_project_id = lambda x: "abcd"

    return MenuForTodoist(
        config=menu_config.todoist,
        final_menu_df=mock_all_menus_df,
        due_date_formatter=frozen_due_datetime_formatter,
        todoist_helper=mock_todoist_helper,
    )


class TestFormatTaskName:
    @staticmethod
    @freeze_time(FROZEN_DATE)
    def test__works_as_expected_for_defrost_case(
        menu_for_todoist, menu_builder
    ):
        row = menu_builder.create_tmp_menu_row(
            item="french onion soup",
            meal_time="dinner",
            time_total_str=pd.to_timedelta("40 min"),
            defrost="Y",
        ).squeeze()
        assert menu_for_todoist._format_task_name(row) == row["item"]

    @staticmethod
    @freeze_time(FROZEN_DATE)
    def test__works_as_expected_for_recipe(menu_for_todoist, menu_builder):
        row = menu_builder.create_tmp_menu_row(
            item="french onion soup",
            meal_time="dinner",
            time_total_str=pd.to_timedelta("40 min"),
        ).squeeze()
        assert menu_for_todoist._format_task_name(row) == (
            f"{row['item']} (x eat: {row.eat_factor}) [40 min]"
        )

    @staticmethod
    @freeze_time(FROZEN_DATE)
    def test__works_as_expected_for_ingredient(menu_for_todoist, menu_builder):
        row = menu_builder.create_tmp_menu_row(
            item="fries",
            item_type="ingredient",
            meal_time="dinner",
        ).squeeze()
        assert menu_for_todoist._format_task_name(row) == (
            f"{row['item']} (x eat: {row.eat_factor}) [20 min]"
        )

    @staticmethod
    @freeze_time(FROZEN_DATE)
    def test__works_as_expected_for_freeze_some_case(
        menu_for_todoist, menu_builder
    ):
        recipe_title = "french onion soup"
        row = menu_builder.create_tmp_menu_row(
            item=recipe_title,
            meal_time="dinner",
            freeze_factor=0.5,
        ).squeeze()
        assert menu_for_todoist._format_task_name(row) == (
            "french onion soup (x eat: 1.0, x freeze: 0.5) [5 min]"
        )
