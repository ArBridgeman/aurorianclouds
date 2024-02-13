from datetime import datetime, timedelta
from typing import List, Tuple

import numpy as np
import pandas as pd
from jellyfin_helpers.jellyfin_api import Jellyfin
from jellyfin_helpers.workout_plan.models import (
    Day,
    PlanTemplate,
    SearchType,
    WorkoutPlan,
    WorkoutVideoSchema,
)
from omegaconf import DictConfig
from pandera.typing.common import DataFrameBase
from structlog import get_logger

from utilities.api.gsheets_api import GsheetsHelper

LOGGER = get_logger(__name__)


# TODO create option to catch videos without tag
# TODO use video file to get duration info


def convert_timedelta_to_min(time_delta: pd.Series) -> int:
    return int(time_delta.dt.total_seconds().values[0] // 60)


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

    @staticmethod
    def _is_value_in_list(row: pd.Series, search_term: str):
        return search_term in row

    def _search_for_workout(
        self, row: pd.Series, skip_ids: List[str]
    ) -> Tuple[List[str], List[str], List[str]]:
        if row.search_type in SearchType.name_list():
            selected_workouts = self._select_exercise_by_key(
                key=row.search_type,
                value=row["values"],
                duration_in_minutes=row.total_in_min,
                skip_ids=skip_ids,
            )
            descriptions = selected_workouts.description.values
            tools = selected_workouts.tool.values
            item_ids = selected_workouts.Id.values
            return descriptions, tools, item_ids
        raise ValueError("Unknown SearchType")

    @staticmethod
    def _select_exercise(
        data: pd.DataFrame, remaining_duration: timedelta
    ) -> pd.DataFrame:
        data = data.copy(deep=True)
        selected_exercises = pd.DataFrame()

        while data.shape[0] > 0 & (remaining_duration > timedelta(minutes=0)):
            # add 1 min to avoid division by 0
            time_diff = (
                remaining_duration + timedelta(minutes=1) - data.Duration
            ).dt.total_seconds() / 60

            # select exercise
            exercise = data.sample(n=1, weights=1 / time_diff.values)
            exercise["description"] = (
                f"{exercise.Name.values[0]}"
                f" ({convert_timedelta_to_min(exercise.Duration)} min)"
            )
            selected_exercises = pd.concat([exercise, selected_exercises])
            # remove it from consideration
            data.drop(exercise.index, inplace=True)
            # update duration
            remaining_duration -= exercise.Duration.values[0]
            data = data[data.Duration <= remaining_duration]
        return selected_exercises

    def _select_exercise_by_key(
        self,
        key: str,
        value: str,
        duration_in_minutes: int,
        skip_ids: List[str],
    ) -> pd.DataFrame:
        duration_timedelta = pd.to_timedelta(f"{duration_in_minutes} minutes")

        mask = np.ones(self.workout_videos.shape[0], dtype=bool)
        if key == "genre":
            mask &= self.workout_videos.Genre.str.lower() == value.lower()
        elif key == "tag":
            mask &= self.workout_videos["Tags"].apply(
                lambda row: self._is_value_in_list(row, value)
            )
        mask = self._add_duration_mask(mask, duration_timedelta)
        mask = self._add_skip_ids_to_mask(mask, skip_ids)

        if (total_found := sum(mask)) == 0:
            raise ValueError(f"no entries found for {key}={value}")
        print(f"({key}={value}, {duration_in_minutes} min): {total_found}")

        return self._select_exercise(
            data=self.workout_videos[mask],
            remaining_duration=duration_timedelta,
        )

    def _add_duration_mask(
        self, mask: pd.Series, duration_timedelta: pd.Timedelta
    ) -> pd.Series:
        return mask & (self.workout_videos.Duration <= duration_timedelta)

    def _add_skip_ids_to_mask(
        self, mask: pd.Series, skip_ids: List[str]
    ) -> pd.Series:
        return mask & ~self.workout_videos.Id.isin(skip_ids)

    def _load_plan_template(
        self, gsheets_helper: GsheetsHelper
    ) -> DataFrameBase[PlanTemplate]:
        plan_template = gsheets_helper.get_worksheet(
            workbook_name=self.app_config.gsheets.workbook,
            worksheet_name=self.app_config.gsheets.template_worksheet,
        )
        plan_template.total_in_min = plan_template.total_in_min.astype("int64")
        # pandera does not replace "" by default, only None
        plan_template.optional.replace("", None, inplace=True)
        plan_template.active.replace("", None, inplace=True)
        return PlanTemplate.validate(plan_template)

    def _load_last_plan(
        self, gsheets_helper: GsheetsHelper
    ) -> DataFrameBase[WorkoutPlan]:
        df = gsheets_helper.get_worksheet(
            workbook_name=self.app_config.gsheets.workbook,
            worksheet_name=self.app_config.gsheets.plan_worksheet,
        )
        return WorkoutPlan.validate(df)

    def create_workout_plan(
        self, gsheets_helper: GsheetsHelper
    ) -> DataFrameBase[WorkoutPlan]:
        template = self._load_plan_template(gsheets_helper=gsheets_helper)
        last_plan = self._load_last_plan(gsheets_helper=gsheets_helper)

        all_skip_ids = list(last_plan.item_id.values)
        in_month_skip_ids = list()
        today_index = Day[datetime.now().strftime("%A").lower()[:3]].value
        plan = pd.DataFrame()
        for _, row in template.iterrows():
            if row.active == "N":
                continue

            start, _ = row.day.split("_")
            # TODO only set correctly for sat/sun/mon
            # better to extract due date formatter shared logic?
            days = int(start) - today_index
            week = max((days // 7) + 1, 1)

            title = row["values"]
            if row.search_type == "reminder":
                print(f"(reminder): {title}")
                new_row = pd.DataFrame(
                    {
                        "day": [days],
                        "week": [week],
                        "title": [title],
                        "source_type": ["reminder"],
                        "total_in_min": [row.total_in_min],
                        "description": [np.NaN],
                        "tool": [np.NaN],
                        "item_id": [np.NaN],
                        "optional": [row.optional],
                    }
                )
            else:
                descriptions, tools, item_ids = self._search_for_workout(
                    row=row,
                    skip_ids=all_skip_ids
                    # currently not enough entries for both of these filters
                    if row["values"] != "tennis/arm" else in_month_skip_ids,
                )
                in_month_skip_ids.extend(item_ids)
                all_skip_ids.extend(item_ids)

                num_entries = len(descriptions)
                new_row = pd.DataFrame(
                    {
                        "day": [days] * num_entries,
                        "week": [week] * num_entries,
                        "title": [title] * num_entries,
                        "source_type": ["video"] * num_entries,
                        "total_in_min": [row.total_in_min] * num_entries,
                        "description": descriptions,
                        "tool": tools,
                        "item_id": item_ids,
                        "optional": [row.optional] * num_entries,
                    }
                )

            plan = pd.concat([plan, new_row])

        return WorkoutPlan.validate(plan).sort_values(by="day")
