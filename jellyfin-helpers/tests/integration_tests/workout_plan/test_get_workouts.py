import pytest
from jellyfin_helpers.jellyfin_api import Jellyfin
from jellyfin_helpers.workout_plan.get_workouts import WorkoutVideos


@pytest.fixture(scope="module")
def jellyfin(config):
    return Jellyfin(config=config.jellyfin)


@pytest.mark.jellyfin
class TestParseWorkoutVideos:
    @staticmethod
    def test_works_as_expected(jellyfin):
        workout_videos = WorkoutVideos(jellyfin=jellyfin)
        workout_videos.parse_workout_videos()
