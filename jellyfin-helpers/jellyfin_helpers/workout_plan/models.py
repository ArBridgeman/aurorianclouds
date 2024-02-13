from datetime import timedelta
from enum import Enum, IntEnum
from typing import List

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


# TODO put enum extensions in utilities
class SearchType(Enum):
    genre = "genre"
    reminder = "reminder"
    tag = "tag"

    @classmethod
    def name_list(cls, string_method: str = "casefold"):
        return list(map(lambda c: getattr(c.name, string_method)(), cls))


class WorkoutVideoSchema(pa.SchemaModel):
    Name: Series[str]
    Id: Series[str]
    Duration: Series[timedelta] = pa.Field(
        ge=timedelta(minutes=0), nullable=False
    )
    Genre: Series[str]
    Tags: Series[List[str]]

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
    total_in_min: Series[int] = pa.Field(
        gt=0, le=60, nullable=False, coerce=True
    )
    description: Series[str] = pa.Field(nullable=True)
    item_id: Series[str] = pa.Field(nullable=True)
    optional: Series[str] = pa.Field(
        isin=["Y", "N"], nullable=False, default="N", coerce=True
    )
