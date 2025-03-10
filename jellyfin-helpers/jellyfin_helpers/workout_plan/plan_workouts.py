from dataclasses import dataclass
from datetime import timedelta
from typing import List

import numpy as np
import pandas as pd
from jellyfin_helpers.jellyfin_api import Jellyfin
from jellyfin_helpers.workout_plan.date_util import RelativeDate
from jellyfin_helpers.workout_plan.models import (
    Difficulty,
    SearchType,
    SetSchema,
    TimePlanSchema,
    WorkoutPlan,
    WorkoutVideoSchema,
)
from omegaconf import DictConfig
from pandera.typing.common import DataFrameBase
from structlog import get_logger

from utilities.api.gsheets_api import GsheetsHelper, WorkBook

LOGGER = get_logger(__name__)


# TODO create option to catch videos without tag
# TODO use video file to get duration info


def convert_timedelta_to_min(time_delta: pd.Series) -> int:
    return int(time_delta.dt.total_seconds().values[0] // 60)


@dataclass
class SearchError(Exception):
    key: str
    value: str
    message: str = "[search failed]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        values = {
            "key": self.key,
            "value": self.value,
        }
        return f"{self.message}: {values}"


class WorkoutPlanner:
    def __init__(
        self,
        app_config: DictConfig,
        jellyfin: Jellyfin,
        workout_videos: DataFrameBase[WorkoutVideoSchema],
    ):
        self.app_config = app_config
        self.jellyfin = jellyfin
        self.workout_videos = workout_videos
        self.error_count = 0

    @staticmethod
    def _is_value_in_list(row: pd.Series, search_term: str):
        return search_term in row

    def _search_for_workout(
        self, row: pd.Series, skip_ids: List[str]
    ) -> pd.DataFrame:
        LOGGER.info(
            "[search_for_workout]",
            type=row["values"],
            highest_difficulty=row.highest_difficulty,
            duration_in_min=row.duration_in_min,
            day=row.day,
        )
        if row.search_type in SearchType.name_list():
            selected_workouts = self._select_exercise_by_key(
                key=row.search_type,
                value=row["values"],
                highest_difficulty_str=row["highest_difficulty"],
                duration_in_minutes=row.duration_in_min,
                skip_ids=skip_ids,
            )
            return selected_workouts
        raise ValueError("Unknown SearchType")

    @staticmethod
    def _select_exercise(
        data: pd.DataFrame, remaining_duration: timedelta
    ) -> pd.DataFrame:
        data = data.copy(deep=True)
        selected_exercises = pd.DataFrame()

        while data.shape[0] > 0 & (remaining_duration > timedelta(minutes=0)):
            duration = data.duration.dt.total_seconds() // 60
            tool = data.tool != ""
            difficulty = np.maximum(
                np.abs(data.difficulty_num), tool.astype(int)
            )
            weights = duration + data.rating * 2 + difficulty * 2

            # select exercise
            exercise = data.sample(n=1, weights=weights)
            exercise["description"] = (
                f"{exercise.name.values[0]}"
                f" ({convert_timedelta_to_min(exercise.duration)} min)"
            )
            selected_exercises = pd.concat([exercise, selected_exercises])
            # remove it from consideration
            data = data.drop(exercise.index)
            # update duration
            remaining_duration -= exercise.duration.values[0]
            data = data[data.duration <= remaining_duration]
        return selected_exercises

    def _select_exercise_by_key(
        self,
        key: str,
        value: str,
        highest_difficulty_str: str,
        duration_in_minutes: int,
        skip_ids: List[str],
    ) -> pd.DataFrame:
        duration_timedelta = pd.to_timedelta(f"{duration_in_minutes} minutes")

        mask = np.ones(self.workout_videos.shape[0], dtype=bool)
        highest_difficulty = Difficulty[highest_difficulty_str].value
        mask &= np.logical_or(
            self.workout_videos.difficulty_num == highest_difficulty,
            self.workout_videos.difficulty_num == Difficulty.normal.value,
        )
        if key == "genre":
            mask &= (
                self.workout_videos.genre.str.strip().str.lower()
                == value.lower()
            )
        elif key == "tag":
            mask &= self.workout_videos["tags"].apply(
                lambda row: self._is_value_in_list(row, value)
            )
        mask = self._add_duration_mask(mask, duration_timedelta)
        mask = self._add_skip_ids_to_mask(mask, skip_ids)

        if (total_found := sum(mask)) == 0:
            raise SearchError(
                key=key,
                value=value,
                message="[select_exercise_by_key] no entries found",
            )
        print(f"({key}={value}, {duration_in_minutes} min): {total_found}")

        return self._select_exercise(
            data=self.workout_videos[mask],
            remaining_duration=duration_timedelta,
        )

    def _add_duration_mask(
        self, mask: pd.Series, duration_timedelta: pd.Timedelta
    ) -> pd.Series:
        return mask & (self.workout_videos.duration <= duration_timedelta)

    def _add_skip_ids_to_mask(
        self, mask: pd.Series, skip_ids: List[str]
    ) -> pd.Series:
        return mask & ~self.workout_videos.id.isin(skip_ids)

    @staticmethod
    def _get_placeholder(
        days_from_now: int, row: pd.Series, source_type: str
    ) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "week": [row.week],
                "day": [days_from_now],
                "source_type": [source_type],
                "key": [row.key],
                "duration_in_min": [row.total_in_min],
                "optional": [row.optional],
                "time_of_day": [row.time_of_day],
                "item_id": [""],
                "description": [""],
                "tool": [""],
            }
        )

    def _load_time_plan(
        self, workbook: WorkBook
    ) -> DataFrameBase[TimePlanSchema]:
        weekly = workbook.get_worksheet(
            worksheet_name=self.app_config.gsheets.worksheet.weekly,
        )
        sleep = workbook.get_worksheet(
            worksheet_name=self.app_config.gsheets.worksheet.sleep,
        )
        plan_template = pd.concat([weekly, sleep])

        # pandera does not replace "" by default, only None
        plan_template["optional"] = plan_template["optional"].replace("", None)
        plan_template["active"] = plan_template["active"].replace("", None)
        return TimePlanSchema.validate(plan_template)

    def _load_sets(self, workbook: WorkBook) -> DataFrameBase[SetSchema]:
        sets = workbook.get_worksheet(
            worksheet_name=self.app_config.gsheets.worksheet.sets,
        )
        return SetSchema.validate(sets)

    def _load_weekly_plan(self, workbook: WorkBook) -> pd.DataFrame:
        time_plan = self._load_time_plan(workbook)
        sets = self._load_sets(workbook)
        weekly_plan = pd.merge(left=time_plan, right=sets, on="key", how="left")
        return weekly_plan.sort_values(by=["day", "time_of_day", "order"])

    def _load_last_plan(self, workbook: WorkBook) -> DataFrameBase[WorkoutPlan]:
        df = workbook.get_worksheet(
            worksheet_name=self.app_config.gsheets.worksheet.plan,
        )
        return WorkoutPlan.validate(df)

    def create_workout_plan(
        self, gsheets_helper: GsheetsHelper
    ) -> DataFrameBase[WorkoutPlan]:
        workbook = gsheets_helper.get_workbook(
            workbook_name=self.app_config.gsheets.workbook,
        )
        weekly_plan = self._load_weekly_plan(workbook=workbook)
        last_plan = self._load_last_plan(workbook=workbook)

        all_skip_ids = list(last_plan.item_id.values)
        in_month_skip_ids = list()
        relative_date = RelativeDate()
        plan = pd.DataFrame()
        for _, row in weekly_plan.iterrows():
            if row.active == "N":
                continue

            day_num = int(row.day.split("_")[0])
            days_from_now = relative_date.get_days_from_now(day_index=day_num)

            if row.entry_type == "reminder":
                print(f"(reminder): {row.key}")
                new_row = self._get_placeholder(
                    days_from_now=days_from_now, row=row, source_type="reminder"
                )
            else:
                try:
                    selected_workouts = self._search_for_workout(
                        row=row, skip_ids=all_skip_ids
                    )
                    item_ids = selected_workouts.id.values
                    in_month_skip_ids.extend(item_ids)
                    all_skip_ids.extend(item_ids)

                    num_entries = selected_workouts.shape[0]
                    new_row = pd.DataFrame(
                        {
                            "week": [row.week] * num_entries,
                            "day": [days_from_now] * num_entries,
                            "source_type": ["video"] * num_entries,
                            "key": [row.key] * num_entries,
                            "duration_in_min": selected_workouts.duration.apply(
                                lambda x: x.seconds // 60
                            ).values,
                            "optional": [row.optional] * num_entries,
                            "time_of_day": [row.time_of_day] * num_entries,
                            "item_id": item_ids,
                            "description": selected_workouts.description.values,
                            "tool": selected_workouts.tool.values,
                        }
                    )
                except SearchError:
                    self.error_count += 1
                    LOGGER.warning(
                        "...failed to find workout matching this criteria"
                    )
                    new_row = self._get_placeholder(
                        days_from_now=days_from_now,
                        row=row,
                        source_type="missing_video",
                    )

                plan = pd.concat([plan, new_row])

        return WorkoutPlan.validate(plan)
