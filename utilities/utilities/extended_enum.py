from enum import Enum, IntEnum
from typing import List


def extend_enum(inherited_enums: List):
    def wrapper(added_enum):
        joined = {}
        for inherited_enum in inherited_enums:
            for item in inherited_enum:
                joined[item.name] = item.value
            for item in added_enum:
                joined[item.name] = item.value
        return Enum(added_enum.__name__, joined)

    return wrapper


class ExtendedEnum(Enum):
    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            value_lower = value.lower()
            for member in cls:
                if member.name.lower() == value_lower:
                    return member
        return None

    @classmethod
    def name_list(cls, string_method: str = "casefold"):
        return list(map(lambda c: getattr(c.name, string_method)(), cls))

    @classmethod
    def value_list(cls, string_method: str = "casefold"):
        return list(map(lambda c: getattr(c.value, string_method)(), cls))


class ExtendedIntEnum(IntEnum):
    @classmethod
    def name_list(cls, string_method: str = "casefold"):
        return list(map(lambda c: getattr(c.name, string_method)(), cls))
