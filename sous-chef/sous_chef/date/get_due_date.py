import datetime
from dataclasses import dataclass, field

from omegaconf import DictConfig
from pytz import timezone
from sous_chef.abstract.extended_enum import ExtendedEnum, ExtendedIntEnum


# TODO make configurable?
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


# TODO make configurable?
class MealTime(ExtendedEnum):
    breakfast = {"hour": 8, "minute": 30}
    lunch = {"hour": 12, "minute": 00}
    snack = {"hour": 15, "minute": 00}
    dinner = {"hour": 16, "minute": 30}
    dessert = {"hour": 19, "minute": 30}


@dataclass
class DueDatetimeFormatter:
    config: DictConfig
    meal_time: MealTime = MealTime
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
        self, weekday: str, hour: int, minute: int
    ) -> datetime.datetime:
        due_date = self.get_date_relative_to_anchor(weekday=weekday)
        return self._set_specified_time(
            due_date=due_date, hour=hour, minute=minute
        )

    def replace_time_with_meal_time(
        self, due_date: datetime.datetime, meal_time: str
    ) -> datetime.datetime:
        hour, minute = self._get_meal_time_hour_minute(meal_time)
        return self._set_specified_time(due_date, hour, minute)

    def set_date_with_meal_time(
        self, due_date: datetime.date, meal_time: str
    ) -> datetime.datetime:
        hour, minute = self._get_meal_time_hour_minute(meal_time)
        time = datetime.time(hour=hour, minute=minute)
        return datetime.datetime.combine(
            due_date, time=time, tzinfo=timezone("UTC")
        )

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
            anchor_date, datetime.datetime.min.time(), tzinfo=timezone("UTC")
        )

    def _get_meal_time_hour_minute(self, meal_time: str) -> (str, str):
        meal_time_dict = self.meal_time[meal_time.casefold()].value
        return meal_time_dict["hour"], meal_time_dict["minute"]

    @staticmethod
    def _set_specified_time(
        due_date: datetime.datetime, hour: int, minute: int
    ) -> datetime.datetime:
        return due_date.replace(hour=hour, minute=minute, second=0)
