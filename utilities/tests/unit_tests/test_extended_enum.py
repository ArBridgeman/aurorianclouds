import pytest

from utilities.extended_enum import ExtendedEnum, ExtendedIntEnum, extend_enum


class TweedleTwins(ExtendedEnum):
    tweedledee = "Tweedledee"
    tweedledum = "Tweedledum"


class WhiteRabbitSays(ExtendedEnum):
    late = "late"
    important = "important"
    date = "date"


WHITE_RABBIT_SAYS_LIST = [
    pytest.param("lower", ["late", "important", "date"], id="lowered"),
    pytest.param("capitalize", ["Late", "Important", "Date"], id="capitalized"),
    pytest.param("casefold", ["late", "important", "date"], id="casefolded"),
    pytest.param("upper", ["LATE", "IMPORTANT", "DATE"], id="uppered"),
]


class TestExtendEnum:
    @staticmethod
    def test_extension_works_as_expected():
        @extend_enum([TweedleTwins, WhiteRabbitSays])
        class SideCharacters(ExtendedEnum):
            pass

        assert (
            SideCharacters._member_names_
            == TweedleTwins._member_names_ + WhiteRabbitSays._member_names_
        )

    @staticmethod
    @pytest.mark.parametrize(
        "string_method,expected_result", WHITE_RABBIT_SAYS_LIST
    )
    def test_name_list_as_expected(string_method, expected_result):
        assert WhiteRabbitSays.name_list(string_method) == expected_result

    @staticmethod
    @pytest.mark.parametrize(
        "string_method,expected_result", WHITE_RABBIT_SAYS_LIST
    )
    def test_value_as_expected(string_method, expected_result):
        assert WhiteRabbitSays.value_list(string_method) == expected_result

    @staticmethod
    def test__missing_works_as_expected():
        value = "LaTE"
        # ensure initial test condition is met
        assert value not in WhiteRabbitSays.name_list("upper")

        assert WhiteRabbitSays(value) == WhiteRabbitSays.late


class WhiteRabbitCounts(ExtendedIntEnum):
    months = 12
    weeks = 52
    days = 365


class TestExtendIntEnum:
    @staticmethod
    @pytest.mark.parametrize(
        "string_method,expected_result",
        [
            ("lower", ["months", "weeks", "days"]),
            ("capitalize", ["Months", "Weeks", "Days"]),
            ("casefold", ["months", "weeks", "days"]),
            ("upper", ["MONTHS", "WEEKS", "DAYS"]),
        ],
    )
    def test_extended_int_enum(string_method, expected_result):
        assert WhiteRabbitCounts.name_list(string_method) == expected_result
