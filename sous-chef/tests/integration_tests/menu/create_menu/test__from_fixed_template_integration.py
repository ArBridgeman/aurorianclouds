import pytest
from sous_chef.menu.create_menu._from_fixed_template import FixedTemplates

from utilities.testing.pandas_util import assert_equal_dataframe


@pytest.fixture(scope="module")
def fixed_templates(
    fixed_menu_config, gsheets_helper, frozen_due_datetime_formatter
):
    fixed_templates = FixedTemplates(
        config=fixed_menu_config.menu.create_menu.fixed,
        due_date_formatter=frozen_due_datetime_formatter,
        gsheets_helper=gsheets_helper,
    )
    return fixed_templates


@pytest.mark.gsheets
class TestFixedTemplates:
    @staticmethod
    def test_get_all_fixed_menus(fixed_templates, fixed_all_menus):
        all_menus_df = fixed_templates._get_all_fixed_menus()
        assert_equal_dataframe(all_menus_df, fixed_all_menus)
