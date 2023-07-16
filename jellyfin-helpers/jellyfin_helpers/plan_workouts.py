from datetime import timedelta
from typing import List

import pandas as pd
import pandera as pa
from jellyfin_helpers.jellyfin_api import Jellyfin
from jellyfin_helpers.utils import get_jellyfin_config
from pandera.typing import Series


class WorkoutVideos(pa.SchemaModel):
    Name: Series[str]
    Id: Series[str]
    Duration: Series[timedelta]
    Genre: Series[str]

    class Config:
        strict = True


# TODO create option to catch videos without tag
# TODO use video file to get duration info
# TODO cache result of _parse_workout_videos


class WorkoutPlanner:
    def __init__(self, jellyfin: Jellyfin):
        self.jellyfin = jellyfin
        self.workout_videos = self._parse_workout_videos()

    @staticmethod
    def _get_duration_from_tags(tags: List[str]) -> timedelta:
        time_tag = list(filter(lambda x: " min" in x, tags))
        if len(time_tag) < 1:
            return timedelta(minutes=-100)
        smaller_time = int(time_tag[0].split("-")[0])
        return timedelta(minutes=smaller_time)

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
                [raw_data[["Name", "Id", "Duration", "Genre"]], data_frame]
            )
            WorkoutVideos.validate(data_frame)
        return data_frame

    def _select_exercise_by_genre(self, genre: str, duration_in_minutes: int):
        remaining_duration = pd.to_timedelta(f"{duration_in_minutes} minutes")
        genre_mask = self.workout_videos.Genre.str.lower() == genre.lower()
        duration_mask = self.workout_videos.Duration <= remaining_duration
        relevant_data = self.workout_videos[genre_mask & duration_mask].copy(
            deep=True
        )

        selected_exercises = pd.DataFrame()
        while relevant_data.shape[0] > 0 & (
            remaining_duration > timedelta(minutes=0)
        ):
            # select exercise
            exercise = relevant_data.sample(n=1)
            selected_exercises = pd.concat([exercise, selected_exercises])
            # remove it from consideration
            relevant_data.drop(exercise.index, inplace=True)
            # update duration
            remaining_duration -= exercise.Duration.values[0]
            relevant_data = relevant_data[
                relevant_data.Duration <= remaining_duration
            ]
        # WHAT TO DO IF GENRE MORE THAN 1 CALLED? HISTORY
        print(selected_exercises)

    def create_workout_plan(self):
        pass


config = get_jellyfin_config()
jellyfin = Jellyfin(config=config)
workout_planner = WorkoutPlanner(jellyfin=jellyfin)
workout_planner._select_exercise_by_genre(genre="Booty", duration_in_minutes=30)
# TODO plan workouts for week just by running & adding to playlist
# TODO create csv or something with workout template to go through
# TODO todoist integration?
