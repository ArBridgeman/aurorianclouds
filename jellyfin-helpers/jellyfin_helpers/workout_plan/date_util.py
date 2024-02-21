from dataclasses import dataclass
from datetime import datetime

from jellyfin_helpers.workout_plan.models import Day


def convert_datetime_to_enum(datetime_value: datetime) -> Day:
    return Day(datetime_value.strftime("%A"))


@dataclass
class RelativeDate:
    today_index = convert_datetime_to_enum(datetime.now()).value

    def get_days_from_now(self, day_index: int) -> int:
        days = day_index - self.today_index + 1
        if self.today_index > Day.mon:
            days += 7
        return days
