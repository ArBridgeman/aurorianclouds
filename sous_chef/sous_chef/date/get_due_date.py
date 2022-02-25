import datetime
from enum import Enum


# TODO move to config?
class Weekday(Enum):
    monday = 0
    tuesday = 1
    wednesday = 2
    thursday = 3
    friday = 4
    saturday = 5
    sunday = 6


class MealTime(Enum):
    breakfast = {"hour": 8, "minute": 30}
    lunch = {"hour": 11, "minute": 30}
    dinner = {"hour": 18, "minute": 15}


class DueDatetimeFormatter:
    # TODO add anchor date, default time in config?
    def __init__(self):
        self.anchor_date = self._get_anchor_date_at_midnight("Friday")

    def get_due_datetime_with_meal_time(self, weekday: str, meal_time: str):
        due_date = self._get_date_relative_to_anchor(weekday=weekday)
        return self._replace_time_with_meal_time(due_date, meal_time)

    def get_due_datetime_with_hour_minute(
        self, weekday: str, hour: int, minute: int
    ):
        due_date = self._get_date_relative_to_anchor(weekday=weekday)
        return self._set_specified_time(
            due_date=due_date, hour=hour, minute=minute
        )

    def _get_anchor_date_at_midnight(self, weekday: str) -> datetime:
        weekday_index = self._get_weekday_index(weekday)
        today = datetime.date.today()
        anchor_date = today + datetime.timedelta(
            days=max(0, weekday_index - today.weekday())
        )
        return datetime.datetime.combine(
            anchor_date, datetime.datetime.min.time()
        )

    def _get_date_relative_to_anchor(self, weekday: str) -> datetime.datetime:
        weekday_index = self._get_weekday_index(weekday)
        # TODO could anchor date and logic here be simplified?
        relative_date = weekday_index - self.anchor_date.weekday() + 7
        due_date = self.anchor_date + datetime.timedelta(days=relative_date % 7)
        if due_date.date() == self.anchor_date.date():
            due_date += datetime.timedelta(days=7)
        return due_date

    @staticmethod
    def _get_meal_time_hour_minute(meal_time: str) -> (str, str):
        # TODO way to have inside MealTime class?
        meal_time_dict = MealTime[meal_time.casefold()].value
        return meal_time_dict["hour"], meal_time_dict["minute"]

    @staticmethod
    def _get_weekday_index(weekday: str):
        # TODO way to have inside Weekday class?
        return Weekday[weekday.casefold()].value

    def _replace_time_with_meal_time(
        self, due_date: datetime.datetime, meal_time: str
    ) -> datetime.datetime:
        hour, minute = self._get_meal_time_hour_minute(meal_time)
        return self._set_specified_time(due_date, hour, minute)

    @staticmethod
    def _set_specified_time(
        due_date: datetime.datetime, hour: int, minute: int
    ) -> datetime.datetime:
        return due_date.replace(hour=hour, minute=minute, second=0)
