from unittest.mock import patch

import pytest
from freezegun import freeze_time
from sous_chef.menu.create_menu._from_fixed_template import FixedTemplates
from tests.conftest import FROZEN_DATE


@pytest.fixture
@freeze_time(FROZEN_DATE)
def fixed_templates(menu_config, gsheets_helper, frozen_due_datetime_formatter):
    with patch.object(FixedTemplates, "__post_init__"):
        fixed_templates = FixedTemplates(
            config=menu_config.fixed,
            due_date_formatter=frozen_due_datetime_formatter,
            gsheets_helper=gsheets_helper,
        )
        return fixed_templates


@pytest.mark.gsheets
class TestFixedTemplates:
    @staticmethod
    def test_get_all_fixed_menus(fixed_templates):
        fixed_templates._get_all_fixed_menus()
