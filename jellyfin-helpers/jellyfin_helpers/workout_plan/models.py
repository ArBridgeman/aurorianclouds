from datetime import timedelta
from enum import Enum, IntEnum, auto
from typing import List, Optional

import pandera as pa
from pandera.typing import Series


class Day(IntEnum):
    sat = 0
    sun = 1
    mon = 2
    tue = 3
    wed = 4
    thu = 5
    fri = 6

    @classmethod
    def _missing_(cls, value: object) -> Optional["Day"]:
        if isinstance(value, str):
            # only select the first 3 values
            value_short = value.lower()[:3]
            for member in cls:
                if value_short == member.name:
                    return member
            return None


class EntryType(Enum):
    reminder = auto()
    set = auto()

    @classmethod
    def name_list(cls, string_method: str = "casefold"):
        return list(map(lambda c: getattr(c.name, string_method)(), cls))


# TODO put enum extensions in utilities
class SearchType(Enum):
    genre = auto()
    tag = auto()

    @classmethod
    def name_list(cls, string_method: str = "casefold"):
        return list(map(lambda c: getattr(c.name, string_method)(), cls))


class Difficulty(IntEnum):
    minus = -1
    normal = 0
    plus = 1

    @classmethod
    def name_list(cls, string_method: str = "casefold"):
        return list(map(lambda c: getattr(c.name, string_method)(), cls))

    @classmethod
    def value_list(cls):
        return list(map(lambda c: c.value, cls))


class WorkoutVideoSchema(pa.SchemaModel):
    name: Series[str]
    id: Series[str]
    duration: Series[timedelta] = pa.Field(
        ge=timedelta(minutes=0), nullable=False
    )
    genre: Series[str]
    tags: Series[List[str]]
    difficulty: Series[str] = pa.Field(isin=Difficulty.name_list("lower"))
    difficulty_num: Series[int] = pa.Field(isin=Difficulty.value_list())
    rating: Series[float]
    tool: Series[str]

    class Config:
        strict = True


week_field = pa.Field(ge=1, le=4, nullable=False, coerce=True)
duration_in_min_field = pa.Field(gt=0, le=75, nullable=False, coerce=True)
optional_field = pa.Field(
    isin=["Y", "N"], nullable=False, default="N", coerce=True
)
time_of_day_field = pa.Field(
    isin=["morning", "afternoon", "evening", "sleep"], nullable=False
)


class TimePlanSchema(pa.SchemaModel):
    week: Series[int] = week_field
    day: Series[str]
    total_in_min: Series[int] = pa.Field(
        gt=0, le=75, nullable=False, coerce=True
    )
    entry_type: Series[str] = pa.Field(isin=EntryType.name_list("lower"))
    key: Series[str]
    highest_difficulty: Series[str] = pa.Field(
        isin=Difficulty.name_list("lower")
    )
    optional: Series[str] = optional_field
    active: Series[str] = pa.Field(
        isin=["Y", "N"], nullable=False, default="Y", coerce=True
    )
    time_of_day: Series[str] = time_of_day_field


class SetSchema(pa.SchemaModel):
    key: Series[str]
    search_type: Series[str] = pa.Field(isin=SearchType.name_list("lower"))
    values: Series[str]
    order: Series[int] = pa.Field(ge=1, le=4, nullable=False, coerce=True)
    duration_in_min: Series[int] = pa.Field(
        ge=5, le=40, nullable=False, coerce=True
    )


class WorkoutPlan(pa.SchemaModel):
    week: Series[int] = week_field
    day: Series[int] = pa.Field(ge=0, le=35, nullable=False, coerce=True)
    source_type: Series[str] = pa.Field(
        isin=["reminder", "video", "missing_video"], nullable=False
    )
    key: Series[str]
    duration_in_min: Series[int] = duration_in_min_field
    optional: Series[str] = optional_field
    time_of_day: Series[str] = time_of_day_field
    item_id: Series[str] = pa.Field(nullable=True)
    description: Series[str] = pa.Field(nullable=True)
    tool: Series[str] = pa.Field(nullable=True)

    class Config:
        strict = True
