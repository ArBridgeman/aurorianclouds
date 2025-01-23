import pytest
from sous_chef.menu.record_menu_history import MenuHistorian
from tests.conftest import FROZEN_DATETIME
from tests.data.util_data import get_final_menu, get_menu_history

from utilities.testing.pandas_util import assert_equal_dataframe


@pytest.fixture(scope="module")
def menu_history(fixed_menu_config, gsheets_helper):
    return MenuHistorian(
        config=fixed_menu_config.menu.record_menu_history,
        gsheets_helper=gsheets_helper,
        current_menu_start_date=FROZEN_DATETIME,
    )


@pytest.mark.gsheets
class TestMenuHistory:
    @staticmethod
    def test_menu_history(menu_history):
        # __post_init__ check
        assert menu_history.dataframe.shape[0] == 0

        menu_history.add_current_menu_to_history(current_menu=get_final_menu())

        menu_history._load_history()
        assert_equal_dataframe(menu_history.dataframe, get_menu_history())

        menu_history._exclude_future_entries()
        assert menu_history.dataframe.shape[0] == 0
