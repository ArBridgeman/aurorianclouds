import pytest
from sous_chef.formatter.format_str import convert_number_to_str


@pytest.mark.parametrize(
    "number,precision,expected_result",
    [(1.124, 2, "1.1"), (1124.23, 2, "1100"), (1, 2, "1"), (100, 2, "100")],
)
def test_convert_float_to_str(number, precision, expected_result):
    assert convert_number_to_str(number, precision) == expected_result
