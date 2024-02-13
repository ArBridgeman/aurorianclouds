import pytest
from jellyfin_helpers.utils import get_config


@pytest.fixture(scope="module")
def config():
    return get_config(config_name="plan_workouts")
