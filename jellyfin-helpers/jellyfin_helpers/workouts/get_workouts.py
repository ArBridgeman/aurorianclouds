import re
from datetime import timedelta
from pathlib import Path
from typing import List, Tuple

import pandas as pd
import pandera as pa
from jellyfin_helpers.jellyfin_api import Jellyfin
from joblib import Memory
from omegaconf import DictConfig
from pandera.typing import Series
from pandera.typing.common import DataFrameBase
from structlog import get_logger

# initialize disk cache
ABS_FILE_PATH = Path(__file__).absolute().parent
CACHE_DIR = ABS_FILE_PATH / "diskcache"
cache = Memory(CACHE_DIR, mmap_mode="r")

LOGGER = get_logger(__name__)


class WorkoutVideoSchema(pa.SchemaModel):
    Name: Series[str]
    Id: Series[str]
    Duration: Series[timedelta] = pa.Field(
        ge=timedelta(minutes=0), nullable=False
    )
    Genre: Series[str]
    Tags: Series[List[str]]

    class Config:
        strict = True


class WorkoutVideos:
    def __init__(self, app_config: DictConfig, jellyfin: Jellyfin):
        self.app_config = app_config
        self.jellyfin = jellyfin

    @staticmethod
    def _get_duration_from_tags(tags: List[str]) -> timedelta:
        time_tag = list(filter(lambda x: " min" in x, tags))
        if len(time_tag) < 1:
            return timedelta(minutes=-100)
        times = re.search(r"(\d+)-(\d+) min", time_tag[0])
        average_time = (int(times.group(1)) + int(times.group(2))) / 2
        return timedelta(minutes=average_time)

    @cache.cache
    def parse_workout_videos(
        self,
        # TODO move to config instead
        library_name: str = "Ariel Fitness",
        skip_genres: Tuple[str] = (
            "Advice",
            "Pregnancy",
            "Injury - Dance Party",
        ),
        debug: bool = False,
    ) -> DataFrameBase[WorkoutVideoSchema]:
        LOGGER.info(f"Querying library={library_name}")

        exercise_genres = self.jellyfin.get_genres_per_library(
            library_name=library_name
        )

        data_frame = pd.DataFrame()
        for genre in exercise_genres:
            if genre["Name"] in skip_genres:
                continue
            LOGGER.info(f"genre={genre['Name']}")
            raw_data = pd.DataFrame(
                self.jellyfin.get_items_per_genre(genre_id=genre["Id"])
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
            if debug:
                LOGGER.info(data_frame)

        return WorkoutVideoSchema.validate(data_frame)
