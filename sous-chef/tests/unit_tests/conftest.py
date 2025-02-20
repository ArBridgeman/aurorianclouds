from collections import namedtuple
from datetime import timedelta
from unittest.mock import Mock, patch
from uuid import uuid1

import pandas as pd
import pytest
from hydra import compose, initialize
from pandera.typing.common import DataFrameBase
from sous_chef.menu.create_menu.models import BasicMenuSchema
from sous_chef.menu.record_menu_history import MenuHistorian
from tests.conftest import FROZEN_DATETIME
from tests.data.util_data import get_all_menus

from utilities.api.gsheets_api import GsheetsHelper
from utilities.api.todoist_api import TodoistHelper


@pytest.fixture
def mock_gsheets():
    with initialize(version_base=None, config_path="../../config/api"):
        config = compose(config_name="gsheets_api")
    with patch.object(GsheetsHelper, "__post_init__"):
        return Mock(GsheetsHelper(config))


@pytest.fixture
def mock_todoist_helper():
    with initialize(version_base=None, config_path="../../config/api"):
        config = compose(config_name="todoist_api")
    with patch.object(TodoistHelper, "__post_init__", lambda x: None):
        return TodoistHelper(config)


HISTORY_ENTRY = namedtuple(
    "Entry", ["cook_datetime", "eat_factor", "item", "uuid"]
)


@pytest.fixture
def config_menu_history():
    with initialize(version_base=None, config_path="../../config/menu"):
        config = compose(config_name="record_menu_history")
    return config.record_menu_history


@pytest.fixture
def mock_menu_history(config_menu_history, mock_gsheets):
    with patch.object(MenuHistorian, "__post_init__"):
        menu_historian = MenuHistorian(
            config_menu_history,
            gsheets_helper=mock_gsheets,
            current_menu_start_date=FROZEN_DATETIME,
        )
    menu_historian.dataframe = pd.DataFrame(
        data=[
            HISTORY_ENTRY(
                FROZEN_DATETIME, 1, "in recent history", str(uuid1())
            ),
            HISTORY_ENTRY(
                FROZEN_DATETIME - timedelta(days=9),
                1,
                "before recent history",
                str(uuid1()),
            ),
        ]
    )
    return menu_historian


@pytest.fixture(scope="session")
def mock_all_menus_df() -> DataFrameBase[BasicMenuSchema]:
    return get_all_menus()
