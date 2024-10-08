from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Tuple

import pandas as pd
from jellyfin_helpers.jellyfin_api import Jellyfin
from jellyfin_helpers.workout_plan.models import Difficulty, WorkoutVideoSchema
from joblib import Memory
from pandera.typing.common import DataFrameBase
from structlog import get_logger

# initialize disk cache
ABS_FILE_PATH = Path(__file__).absolute().parent
CACHE_DIR = ABS_FILE_PATH / "diskcache"
cache = Memory(CACHE_DIR, mmap_mode="r")

LOGGER = get_logger(__name__)
DEFAULT_TIME = timedelta(minutes=-100)


class WorkoutVideos:
    def __init__(self, jellyfin: Jellyfin):
        self.jellyfin = jellyfin

    def parse_workout_videos(self):
        return _parse_workout_videos(jellyfin=self.jellyfin)


class TagExtractor:
    @staticmethod
    def _get_difficulty_from_tags(tags: List[str]) -> Tuple[str, int]:
        difficulty_str = "difficulty/"
        difficulty = list(filter(lambda x: difficulty_str in x, tags))
        if len(difficulty) > 1:
            raise ValueError(
                f"difficulty can only have 1 value, but was {difficulty}"
            )
        # TODO panderas cannot handle enums properly so double-cast :/
        elif len(difficulty) == 1:
            difficulty = difficulty[0].replace(difficulty_str, "")
            difficulty_enum = Difficulty[difficulty]
            return difficulty_enum.name, difficulty_enum.value
        return Difficulty.normal.name, Difficulty.normal.value

    @staticmethod
    def _get_rating_from_tags(tags: List[str]) -> float:
        rating_str = "stars/"
        rating = list(filter(lambda x: rating_str in x, tags))
        if len(rating) > 1:
            raise ValueError(f"rating can only have 1 value, but was {rating}")
        elif len(rating) == 1:
            rating = rating[0].replace(rating_str, "")
            return float(rating)
        return 3.0

    @staticmethod
    def _get_tools_from_tag(tags: List[str]) -> str:
        tool_str = "tool/"
        tools = list(filter(lambda x: tool_str in x, tags))
        if len(tools) < 1:
            return ""
        return ", ".join(tool.replace(tool_str, "") for tool in tools)

    @staticmethod
    def extract_tags(tags: List[str]) -> Tuple[str, int, float, str]:
        if not isinstance(tags, list):
            raise ValueError("tags must be a list of strings")

        difficulty, difficulty_num = TagExtractor._get_difficulty_from_tags(
            tags
        )
        rating = TagExtractor._get_rating_from_tags(tags)
        tools = TagExtractor._get_tools_from_tag(tags)
        return difficulty, difficulty_num, rating, tools


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
    columns_to_extract = WorkoutVideoSchema.to_schema().columns.keys()

    data_frame = pd.DataFrame()
    for genre in exercise_genres:
        if genre["Name"] in skip_genres:
            continue
        LOGGER.info(f"genre={genre['Name']}")
        raw_data = pd.DataFrame(
            jellyfin.get_items_per_genre(genre_id=genre["Id"])
        )
        raw_data = raw_data[~raw_data.VideoType.isna()]
        # duration in minutes
        raw_data["duration"] = pd.to_timedelta(
            raw_data["RunTimeTicks"] / 10**7 / 60, unit="m"
        )
        raw_data["genre"] = genre["Name"]
        raw_data[
            ["difficulty", "difficulty_num", "rating", "tool"]
        ] = raw_data.apply(
            lambda x: TagExtractor.extract_tags(x["Tags"]),
            axis=1,
            result_type="expand",
        )

        raw_data.columns = raw_data.columns.str.lower()

        data_frame = pd.concat(
            [
                raw_data[columns_to_extract],
                data_frame,
            ]
        )
        if debug:
            LOGGER.info(data_frame)

    return WorkoutVideoSchema.validate(data_frame)
