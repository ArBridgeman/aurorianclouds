import pytest
from sous_chef.formatter.format_unit import UnitFormatter


@pytest.fixture
def unit_formatter():
    return UnitFormatter()
