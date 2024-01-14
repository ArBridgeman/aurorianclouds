from datetime import datetime, timedelta
from enum import Enum, IntEnum
from pathlib import Path
from typing import List, Tuple

import pandas as pd
import pandera as pa
from jellyfin_helpers.jellyfin_api import Jellyfin
from jellyfin_helpers.utils import get_config
from jellyfin_helpers.workouts.get_workouts import (
    WorkoutVideos,
    WorkoutVideoSchema,
)
from joblib import Memory
from omegaconf import DictConfig
from pandera.typing import Series
from pandera.typing.common import DataFrameBase
from structlog import get_logger

from utilities.api.gsheets_api import GsheetsHelper
from utilities.api.todoist_api import TodoistHelper

# initialize disk cache
ABS_FILE_PATH = Path(__file__).absolute().parent
CACHE_DIR = ABS_FILE_PATH / "diskcache"
cache = Memory(CACHE_DIR, mmap_mode="r")

LOGGER = get_logger(__name__)


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


class WorkoutPlan(pa.SchemaModel):
    day: Series[str]
    total_in_min: Series[int] = pa.Field(gt=0, le=60, nullable=False)
    search_type: Series[str] = pa.Field(isin=SearchType.name_list("lower"))
    values: Series[str]
    active: Series[str] = pa.Field(isin=["Y", "N"], nullable=False)


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
    ) -> Tuple[str, List[str]]:
        if row.search_type == SearchType.genre.value:
            selected_workouts = self._select_exercise_by_genre(
                genre=row["values"],
                duration_in_minutes=row.total_in_min,
                skip_ids=skip_ids,
            )
            description = "\n".join(selected_workouts.description.values)
            item_ids = selected_workouts.Id.values
            return description, item_ids
        elif row.search_type == SearchType.tag.value:
            selected_workouts = self._select_exercise_by_tag(
                tag=row["values"],
                duration_in_minutes=row.total_in_min,
                skip_ids=skip_ids,
            )
            description = "\n".join(selected_workouts.description.values)
            item_ids = selected_workouts.Id.values
            return description, item_ids
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
        # TODO use history & set random seed when running
        return selected_exercises

    def _select_exercise_by_genre(
        self, genre: str, duration_in_minutes: int, skip_ids: List[str]
    ) -> pd.DataFrame:
        duration_timedelta = pd.to_timedelta(f"{duration_in_minutes} minutes")
        mask = self.workout_videos.Genre.str.lower() == genre.lower()
        mask &= self.workout_videos.Duration <= duration_timedelta
        mask &= ~self.workout_videos.Id.isin(skip_ids)

        if (total_found := sum(mask)) == 0:
            raise ValueError(f"no entries found for genre={genre}")
        print(f"(genre={genre}, {duration_in_minutes} min): {total_found}")

        return self._select_exercise(
            data=self.workout_videos[mask],
            remaining_duration=duration_timedelta,
        )

    def _select_exercise_by_tag(
        self, tag: str, duration_in_minutes: int, skip_ids: List[str]
    ) -> pd.DataFrame:
        duration_timedelta = pd.to_timedelta(f"{duration_in_minutes} minutes")
        mask = self.workout_videos["Tags"].apply(
            lambda row: self._is_value_in_list(row, tag)
        )
        mask &= self.workout_videos.Duration <= duration_timedelta
        mask &= ~self.workout_videos.Id.isin(skip_ids)

        if (total_found := sum(mask)) == 0:
            raise ValueError(f"no entries found for tag={tag}")
        print(f"(tag={tag}, {duration_in_minutes} min): {total_found}")

        return self._select_exercise(
            data=self.workout_videos[mask],
            remaining_duration=duration_timedelta,
        )

    def create_workout_plan(
        self, gsheets_helper: GsheetsHelper, todoist_helper: TodoistHelper
    ):
        workout = gsheets_helper.get_worksheet(
            workbook_name=self.app_config.gsheets.workbook,
            worksheet_name=self.app_config.gsheets.worksheet,
        )
        workout.total_in_min = workout.total_in_min.astype("int64")
        WorkoutPlan.validate(workout)

        today_index = Day[datetime.now().strftime("%A").lower()[:3]].value
        selection_month = []
        for _, row in workout.iterrows():
            if row.active == "N":
                continue

            start, day_str = row.day.split("_")

            # TODO only set correctly for sat/sun/mon
            # better to extract due date formatter shared logic?
            days = int(start) - today_index
            week = max((days // 7) + 1, 1)
            playlist_name = self.app_config.jellyfin[f"playlist_{week}"]
            day_str = f"in {days} days"

            description, item_ids = self._search_for_workout(
                row, selection_month
            )
            selection_month.extend(item_ids)

            self.jellyfin.post_add_to_playlist(
                playlist_name=playlist_name, item_ids=item_ids
            )

            todoist_helper.add_task_to_project(
                task=f"[wk {week}] {row['values']} ({row.total_in_min} min)",
                due_string=day_str,
                project=self.app_config.todoist.project,
                section=self.app_config.todoist.section,
                description=description,
                priority=self.app_config.todoist.task_priority,
                label_list=["health"],
            )


config = get_config(config_name="plan_workouts")

jellyfin_helper = Jellyfin(config=config.jellyfin_api)

# todo separate out configs
workout_videos_df = WorkoutVideos(
    app_config=config.plan_workouts, jellyfin=jellyfin_helper
).parse_workout_videos()

workout_planner = WorkoutPlanner(
    app_config=config.plan_workouts,
    jellyfin=jellyfin_helper,
    workout_videos=workout_videos_df,
)
workout_planner.create_workout_plan(
    gsheets_helper=GsheetsHelper(config=config.gsheets),
    todoist_helper=TodoistHelper(config=config.todoist),
)
