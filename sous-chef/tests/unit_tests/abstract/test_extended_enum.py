import pytest
from sous_chef.abstract.extended_enum import (
    ExtendedEnum,
    ExtendedIntEnum,
    extend_enum,
)


class TweedleTwins(ExtendedEnum):
    tweedledee = "Tweedledee"
    tweedledum = "Tweedledum"


class WhiteRabbitSays(ExtendedEnum):
    late = "late"
    important = "important"
    date = "date"


class WhiteRabbitCounts(ExtendedIntEnum):
    months = 12
    weeks = 52
    days = 365


def test_extend_enum():
    @extend_enum([TweedleTwins, WhiteRabbitSays])
    class SideCharacters(ExtendedEnum):
        pass

    assert (
        SideCharacters._member_names_
        == TweedleTwins._member_names_ + WhiteRabbitSays._member_names_
    )


@pytest.mark.parametrize(
    "string_method,expected_result",
    [
        ("lower", ["late", "important", "date"]),
        ("capitalize", ["Late", "Important", "Date"]),
        ("casefold", ["late", "important", "date"]),
        ("upper", ["LATE", "IMPORTANT", "DATE"]),
    ],
)
def test_extended_enum(string_method, expected_result):
    assert WhiteRabbitSays.name_list(string_method) == expected_result


@pytest.mark.parametrize(
    "string_method,expected_result",
    [
        ("lower", ["late", "important", "date"]),
        ("capitalize", ["Late", "Important", "Date"]),
        ("casefold", ["late", "important", "date"]),
        ("upper", ["LATE", "IMPORTANT", "DATE"]),
    ],
)
def test_extended_enum_values(string_method, expected_result):
    assert WhiteRabbitSays.value_list(string_method) == expected_result


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


def test_extended_enum_cap():
    assert WhiteRabbitSays("LATE") == WhiteRabbitSays.late
