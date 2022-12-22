import datetime

from abstract.extended_enum import ExtendedEnum, ExtendedIntEnum
from pytz import timezone


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
    dinner = {"hour": 17, "minute": 45}


class DueDatetimeFormatter:
    def __init__(self, anchor_day: str):
        self.anchor_datetime = self._get_anchor_date_at_midnight(anchor_day)
        self.meal_time = MealTime

    def get_anchor_date(self) -> datetime.date:
        return self.anchor_datetime.date()

    def get_calendar_week(self) -> int:
        return self.anchor_datetime.isocalendar().week

    def get_date_relative_to_anchor(self, weekday: str) -> datetime.datetime:
        weekday_index = get_weekday_index(weekday)
        # TODO could anchor date and logic here be simplified?
        relative_date = weekday_index - self.anchor_datetime.weekday() + 7
        due_date = self.anchor_datetime + datetime.timedelta(
            days=relative_date % 7
        )
        if due_date.date() <= self.anchor_datetime.date():
            due_date += datetime.timedelta(days=7)
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

    @staticmethod
    def _get_anchor_date_at_midnight(weekday: str) -> datetime.datetime:
        weekday_index = get_weekday_index(weekday)
        today = datetime.date.today()
        anchor_date = today + datetime.timedelta(
            days=max(0, weekday_index - today.weekday())
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
