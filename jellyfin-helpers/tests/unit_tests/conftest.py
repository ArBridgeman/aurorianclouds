from datetime import datetime

import pytest
from freezegun import freeze_time


# Define a fixture to freeze time for the tests
@pytest.fixture(scope="module")
def frozen_time():
    with freeze_time("2023-01-01 12:00:00"):
        yield


@pytest.fixture(scope="module")
def today(frozen_time):
    return datetime.now()
