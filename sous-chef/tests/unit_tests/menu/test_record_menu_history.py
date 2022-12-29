import uuid
from collections import namedtuple
from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest
from hydra import compose, initialize
from sous_chef.menu.record_menu_history import MenuHistorian
from tests.conftest import FROZEN_DATE
from tests.util import assert_equal_series

FROZEN_DATETIME = datetime.strptime(FROZEN_DATE, "%Y-%m-%d")
HISTORY_ENTRY = namedtuple(
    "Entry", ["cook_datetime", "eat_factor", "item", "uuid"]
)


@pytest.fixture
def config_menu_history():
    with initialize(version_base=None, config_path="../../../config/menu"):
        config = compose(config_name="record_menu_history")
        return config.record_menu_history


@pytest.fixture
def menu_history(config_menu_history, mock_gsheets):
    with patch.object(MenuHistorian, "__post_init__"):
        return MenuHistorian(
            config_menu_history,
            gsheets_helper=mock_gsheets,
            current_menu_start_date=FROZEN_DATETIME,
        )


class TestMenuHistory:
    @staticmethod
    def test_get_history_from(menu_history):
        menu_history.dataframe = pd.DataFrame(
            data=[
                HISTORY_ENTRY(
                    FROZEN_DATETIME, 1, "in recent history", str(uuid.uuid1())
                ),
                HISTORY_ENTRY(
                    FROZEN_DATETIME - timedelta(days=9),
                    1,
                    "before recent history",
                    str(uuid.uuid1()),
                ),
            ]
        )

        assert_equal_series(
            menu_history.get_history_from(days_ago=7).squeeze(),
            menu_history.dataframe.loc[0],
        )
