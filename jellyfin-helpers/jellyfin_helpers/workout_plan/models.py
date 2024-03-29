from datetime import timedelta
from enum import Enum, IntEnum
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


# TODO put enum extensions in utilities
class SearchType(Enum):
    genre = "genre"
    reminder = "reminder"
    tag = "tag"

    @classmethod
    def name_list(cls, string_method: str = "casefold"):
        return list(map(lambda c: getattr(c.name, string_method)(), cls))


class WorkoutVideoSchema(pa.SchemaModel):
    name: Series[str]
    id: Series[str]
    duration: Series[timedelta] = pa.Field(
        ge=timedelta(minutes=0), nullable=False
    )
    genre: Series[str]
    tags: Series[List[str]]
    tool: Series[str]

    class Config:
        strict = True


class PlanTemplate(pa.SchemaModel):
    day: Series[str]
    total_in_min: Series[int] = pa.Field(gt=0, le=75, nullable=False)
    search_type: Series[str] = pa.Field(isin=SearchType.name_list("lower"))
    values: Series[str]
    optional: Series[str] = pa.Field(
        isin=["Y", "N"], nullable=False, default="N", coerce=True
    )
    active: Series[str] = pa.Field(
        isin=["Y", "N"], nullable=False, default="Y", coerce=True
    )


class WorkoutPlan(pa.SchemaModel):
    day: Series[int] = pa.Field(ge=0, le=28, nullable=False, coerce=True)
    week: Series[int] = pa.Field(gt=0, le=4, nullable=False, coerce=True)
    title: Series[str]
    source_type: Series[str] = pa.Field(
        isin=["reminder", "video"], nullable=False
    )
    total_in_min: Series[int] = pa.Field(
        gt=0, le=75, nullable=False, coerce=True
    )
    description: Series[str] = pa.Field(nullable=True)
    tool: Series[str] = pa.Field(nullable=True)
    item_id: Series[str] = pa.Field(nullable=True)
    optional: Series[str] = pa.Field(
        isin=["Y", "N"], nullable=False, default="N", coerce=True
    )

    class Config:
        strict = True
