import pytest
from hydra import compose, initialize
from sous_chef.formatter.format_unit import UnitFormatter


@pytest.fixture
def unit_formatter():
    with initialize(config_path="../../config/formatter"):
        config = compose(config_name="format_unit")
        return UnitFormatter(config.format_unit)
