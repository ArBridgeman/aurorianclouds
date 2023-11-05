import re
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from typing import List

import pandas as pd
import pandera as pa
from jellyfin_helpers.jellyfin_api import Jellyfin
from jellyfin_helpers.utils import get_config
from omegaconf import DictConfig
from pandera.typing import Series

from utilities.api.gsheets_api import GsheetsHelper
from utilities.api.todoist_api import TodoistHelper


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


class WorkoutVideos(pa.SchemaModel):
    Name: Series[str]
    Id: Series[str]
    Duration: Series[timedelta] = pa.Field(
        ge=timedelta(minutes=0), nullable=False
    )
    Genre: Series[str]
    Tags: Series[List[str]]

    class Config:
        strict = True


# TODO create option to catch videos without tag
# TODO use video file to get duration info
# TODO cache result of _parse_workout_videos


def convert_timedelta_to_min(time_delta: pd.Series) -> int:
    return int(time_delta.dt.total_seconds().values[0] // 60)


class WorkoutPlanner:
    def __init__(self, app_config: DictConfig, jellyfin: Jellyfin):
        self.app_config = app_config
        self.jellyfin = jellyfin
        self.workout_videos = self._parse_workout_videos()

    @staticmethod
    def _is_value_in_list(row: pd.Series, search_term: str):
        return search_term in row

    @staticmethod
    def _get_duration_from_tags(tags: List[str]) -> timedelta:
        time_tag = list(filter(lambda x: " min" in x, tags))
        if len(time_tag) < 1:
            return timedelta(minutes=-100)
        times = re.search(r"(\d+)-(\d+) min", time_tag[0])
        average_time = (int(times.group(1)) + int(times.group(2))) / 2
        return timedelta(minutes=average_time)

    def _parse_workout_videos(self):
        exercise_genres = jellyfin.get_genres_per_library(
            library_name="Ariel Fitness"
        )

        data_frame = pd.DataFrame()
        for genre in exercise_genres:
            if genre["Name"] in ["Advice", "Pregnancy", "Injury - Dance Party"]:
                continue
            print(f"genre={genre['Name']}")
            raw_data = pd.DataFrame(
                jellyfin.get_items_per_genre(genre_id=genre["Id"])
            )
            raw_data = raw_data[~raw_data.VideoType.isna()]
            raw_data["Duration"] = raw_data["Tags"].apply(
                self._get_duration_from_tags
            )
            raw_data["Genre"] = genre["Name"]

            data_frame = pd.concat(
                [
                    raw_data[["Name", "Id", "Duration", "Genre", "Tags"]],
                    data_frame,
                ]
            )
            # debug
            # print(data_frame)
            WorkoutVideos.validate(data_frame)
        return data_frame

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

    def _select_exercise_by_genre(self, genre: str, duration_in_minutes: int):
        duration_timedelta = pd.to_timedelta(f"{duration_in_minutes} minutes")
        mask = self.workout_videos.Genre.str.lower() == genre.lower()
        mask &= self.workout_videos.Duration <= duration_timedelta

        if (total_found := sum(mask)) == 0:
            raise ValueError(f"no entries found for genre={genre}")
        print(f"(genre={genre}, {duration_in_minutes} min): {total_found}")

        return self._select_exercise(
            data=self.workout_videos[mask],
            remaining_duration=duration_timedelta,
        )

    def _select_exercise_by_tag(self, tag: str, duration_in_minutes: int):
        duration_timedelta = pd.to_timedelta(f"{duration_in_minutes} minutes")
        mask = self.workout_videos["Tags"].apply(
            lambda row: self._is_value_in_list(row, tag)
        )
        mask &= self.workout_videos.Duration <= duration_timedelta

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
        for _, row in workout.iterrows():
            if row.active == "N":
                continue

            start, day_str = row.day.split("_")

            # TODO only set correctly for sat/sun/mon
            # better to extract due date formatter shared logic?
            days = int(start) - today_index
            week = (days // 7) + 1
            playlist_name = self.app_config.jellyfin[f"playlist_{week}"]
            day_str = f"in {days} days"

            description = None
            item_ids = None
            if row.search_type == SearchType.genre.value:
                selected_workouts = self._select_exercise_by_genre(
                    genre=row["values"], duration_in_minutes=row.total_in_min
                )
                description = "\n".join(selected_workouts.description.values)
                item_ids = selected_workouts.Id.values
            elif row.search_type == SearchType.tag.value:
                selected_workouts = self._select_exercise_by_tag(
                    tag=row["values"], duration_in_minutes=row.total_in_min
                )
                description = "\n".join(selected_workouts.description.values)
                item_ids = selected_workouts.Id.values

            if item_ids is not None:
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

jellyfin = Jellyfin(config=config.jellyfin_api)
workout_planner = WorkoutPlanner(
    app_config=config.plan_workouts, jellyfin=jellyfin
)
workout_planner.create_workout_plan(
    gsheets_helper=GsheetsHelper(config=config.gsheets),
    todoist_helper=TodoistHelper(config=config.todoist),
)
