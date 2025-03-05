import pytest
from sous_chef.menu.create_menu._select_menu_template import MenuTemplates

from utilities.testing.pandas_util import assert_equal_dataframe


@pytest.fixture(scope="module")
def menu_templates(
    fixed_menu_config, gsheets_helper, frozen_due_datetime_formatter
):
    fixed_templates = MenuTemplates(
        config=fixed_menu_config.menu.create_menu.fixed,
        due_date_formatter=frozen_due_datetime_formatter,
        gsheets_helper=gsheets_helper,
    )
    return fixed_templates


@pytest.mark.gsheets
class TestMenuTemplates:
    @staticmethod
    def test_get_all_menu_templates(menu_templates, fixed_all_menus):
        assert_equal_dataframe(menu_templates.all_menus_df, fixed_all_menus)
