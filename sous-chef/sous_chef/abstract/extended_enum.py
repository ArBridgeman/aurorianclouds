from enum import Enum, IntEnum


class ExtendedEnum(Enum):
    @classmethod
    def name_list(cls, string_method: str = "casefold"):
        return list(map(lambda c: getattr(c.name, string_method)(), cls))


class ExtendedIntEnum(IntEnum):
    @classmethod
    def name_list(cls, string_method: str = "casefold"):
        return list(map(lambda c: getattr(c.name, string_method)(), cls))
