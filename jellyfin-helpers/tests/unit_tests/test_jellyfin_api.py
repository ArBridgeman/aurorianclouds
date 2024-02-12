from collections import OrderedDict

import pytest
from jellyfin_helpers.jellyfin_api import (
    _build_url,
    _compare_strings,
    _convert_parameter_value_to_string,
)
from pydantic import HttpUrl, parse_obj_as


@pytest.fixture(scope="module")
def server_url():
    return parse_obj_as(HttpUrl, "https://google.com")


class TestBuildUrl:
    @staticmethod
    @pytest.mark.parametrize(
        "kwargs,expected_query",
        [
            pytest.param(OrderedDict(), "", id="path_without_kwargs"),
            pytest.param(
                OrderedDict({"x": "124a"}), "?x=124a", id="path_with_1_kwarg"
            ),
            pytest.param(
                OrderedDict({"x": "124a", "y": "aeg15"}),
                "?x=124a&y=aeg15",
                id="path_with_more_than_1_kwarg",
            ),
        ],
    )
    def test_works_as_expected(server_url, kwargs, expected_query):
        expected_url = f"{server_url}/items" + expected_query
        assert (
            _build_url(server_url=server_url, path="items", kwargs=kwargs)
            == expected_url
        )


class TestConvertParameterValueToString:
    @staticmethod
    @pytest.mark.parametrize(
        "value,expectation",
        [
            pytest.param("string", "string", id="str"),
            pytest.param(["1", "2", "3"], "1,2,3", id="list-of-str"),
            pytest.param(True, "True", id="bool"),
            pytest.param(1, "1", id="int"),
        ],
    )
    def test_works_as_expected(value, expectation):
        assert _convert_parameter_value_to_string(value) == expectation

    @staticmethod
    @pytest.mark.parametrize(
        "value", [pytest.param([1, 2, 3, 4], id="list-of-ints")]
    )
    def test_fails_for_unexpected_cases(value):
        with pytest.raises(TypeError):
            _convert_parameter_value_to_string(value)


class TestCompareStrings:
    @staticmethod
    @pytest.mark.parametrize(
        "str1,str2,expectation",
        [
            pytest.param("same", "same", True, id="identical_string"),
            pytest.param("same", "SaMe", True, id="mixed_case_string"),
            pytest.param(
                "same", "  same ", True, id="with_trailing_space_string"
            ),
            pytest.param("same", "not same ", False, id="different_string"),
            pytest.param("same", "s ame ", False, id="with_inner_space_string"),
        ],
    )
    def test_works_as_expected(str1, str2, expectation):
        assert _compare_strings(str1, str2) == expectation
