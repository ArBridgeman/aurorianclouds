import datetime
from dataclasses import dataclass, field

from omegaconf import DictConfig
from pytz import timezone
from sous_chef.abstract.extended_enum import ExtendedEnum, ExtendedIntEnum

DEFAULT_TIMEZONE = timezone("UTC")


class Weekday(ExtendedIntEnum):
    monday = 0
    tuesday = 1
    wednesday = 2
    thursday = 3
    friday = 4
    saturday = 5
    sunday = 6


def get_weekday_index(weekday: str) -> int:
    return Weekday[weekday.casefold()]


class MealTime(ExtendedEnum):
    breakfast = datetime.time(hour=8, minute=30, tzinfo=DEFAULT_TIMEZONE)
    lunch = datetime.time(hour=12, minute=0, tzinfo=DEFAULT_TIMEZONE)
    snack = datetime.time(hour=15, minute=0, tzinfo=DEFAULT_TIMEZONE)
    dinner = datetime.time(hour=16, minute=30, tzinfo=DEFAULT_TIMEZONE)
    dessert = datetime.time(hour=19, minute=30, tzinfo=DEFAULT_TIMEZONE)


@dataclass
class DueDatetimeFormatter:
    config: DictConfig
    anchor_day: str = field(init=False)
    week_offset: int = field(init=False)
    anchor_datetime: datetime.datetime = None

    def __post_init__(self):
        self.anchor_day = self.config.anchor_day
        self.week_offset = self.config.week_offset
        self.anchor_datetime = self._get_anchor_date_at_midnight()

    def get_anchor_date(self) -> datetime.date:
        return self.anchor_datetime.date()

    def get_anchor_datetime(self) -> datetime.datetime:
        return self.anchor_datetime

    def get_calendar_week(self) -> int:
        return self.anchor_datetime.isocalendar().week

    def get_date_relative_to_anchor(self, weekday: str) -> datetime.datetime:
        weekday_index = get_weekday_index(weekday)
        # relative_date is always positive and in range [1, 13]
        # modulo 7 causes it to always be the nearest following weekday
        # the due_date can never be < anchor_date BUT it can be the same day
        relative_date = weekday_index - self.anchor_datetime.weekday() + 7
        due_date = self.anchor_datetime + datetime.timedelta(
            days=relative_date % 7
        )
        return due_date

    def get_due_datetime_with_meal_time(
        self, weekday: str, meal_time: str
    ) -> datetime.datetime:
        due_date = self.get_date_relative_to_anchor(weekday=weekday)
        return self.replace_time_with_meal_time(due_date, meal_time)

    def get_due_datetime_with_time(
        self, weekday: str, time: datetime.time
    ) -> datetime.datetime:
        due_date = self.get_date_relative_to_anchor(weekday=weekday)
        return self._set_specified_time(due_date=due_date, meal_time=time)

    def replace_time_with_meal_time(
        self, due_date: datetime.datetime, meal_time: str
    ) -> datetime.datetime:
        meal_time = self._get_meal_time(meal_time)
        return self._set_specified_time(due_date, meal_time)

    def _get_anchor_date_at_midnight(self) -> datetime.datetime:
        weekday_index = get_weekday_index(self.anchor_day)
        today = datetime.date.today()
        today_index = today.weekday()

        # by default (week_offset=1) anchor_day will be in the upcoming week,
        # independent of the current weekday.
        # week_offset can be set to an arbitrarily higher (or smaller) number.
        # an anchor day in the same week can be enforced with week_offset=0
        # unless that day has already passed,
        # then it will switch to the next week
        # = same behaviour as with week_offset=1
        # if a past anchor day is really desired (not an expected use case),
        # a negative value of week_offset can be specified
        if (today_index > weekday_index) and self.week_offset < 1:
            weekday_index += 7

        anchor_date = today + datetime.timedelta(
            days=weekday_index - today_index + self.week_offset * 7
        )
        return datetime.datetime.combine(
            anchor_date, datetime.datetime.min.time(), tzinfo=DEFAULT_TIMEZONE
        )

    @staticmethod
    def _get_meal_time(meal_time: str) -> datetime.time:
        return MealTime[meal_time.casefold()].value

    @staticmethod
    def _set_specified_time(
        due_date: datetime.datetime, meal_time: datetime.time
    ) -> datetime.datetime:
        return due_date.combine(date=due_date, time=meal_time)
