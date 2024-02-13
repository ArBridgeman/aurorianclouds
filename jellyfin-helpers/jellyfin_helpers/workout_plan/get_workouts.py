import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Tuple

import pandas as pd
from jellyfin_helpers.jellyfin_api import Jellyfin
from jellyfin_helpers.workout_plan.models import WorkoutVideoSchema
from joblib import Memory
from pandera.typing.common import DataFrameBase
from structlog import get_logger

# initialize disk cache
ABS_FILE_PATH = Path(__file__).absolute().parent
CACHE_DIR = ABS_FILE_PATH / "diskcache"
cache = Memory(CACHE_DIR, mmap_mode="r")

LOGGER = get_logger(__name__)


class WorkoutVideos:
    def __init__(self, jellyfin: Jellyfin):
        self.jellyfin = jellyfin

    @staticmethod
    def get_duration_from_tags(tags: List[str]) -> timedelta:
        time_tag = list(filter(lambda x: " min" in x, tags))
        if len(time_tag) < 1:
            return timedelta(minutes=-100)
        times = re.search(r"(\d+)-(\d+) min", time_tag[0])
        average_time = (int(times.group(1)) + int(times.group(2))) / 2
        return timedelta(minutes=average_time)

    def parse_workout_videos(self):
        return _parse_workout_videos(jellyfin=self.jellyfin)


@cache.cache
def _parse_workout_videos(
    jellyfin: Jellyfin,
    library_name: str = "Ariel Fitness",
    skip_genres: Tuple[str] = (
        "Advice",
        "Pregnancy",
        "Injury - Dance Party",
    ),
    cache_date: date = datetime.today().date(),
    debug: bool = False,
) -> DataFrameBase[WorkoutVideoSchema]:
    LOGGER.info(f"Querying library={library_name}")
    LOGGER.info(f"using cache for {cache_date}")

    exercise_genres = jellyfin.get_genres_per_library(library_name=library_name)

    data_frame = pd.DataFrame()
    for genre in exercise_genres:
        if genre["Name"] in skip_genres:
            continue
        LOGGER.info(f"genre={genre['Name']}")
        raw_data = pd.DataFrame(
            jellyfin.get_items_per_genre(genre_id=genre["Id"])
        )
        raw_data = raw_data[~raw_data.VideoType.isna()]
        raw_data["Duration"] = raw_data["Tags"].apply(
            WorkoutVideos.get_duration_from_tags
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
