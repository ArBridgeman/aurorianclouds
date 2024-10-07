from unittest.mock import Mock

import pandas as pd
import pytest
from jellyfin_helpers.jellyfin_api import Jellyfin
from jellyfin_helpers.workout_plan.plan_workouts import WorkoutPlanner

from utilities.api.gsheets_api import GsheetsHelper


@pytest.fixture(scope="module")
def jellyfin_mock():
    return Mock(Jellyfin)


@pytest.fixture(scope="module")
def workout_videos_df():
    return pd.DataFrame()


@pytest.fixture(scope="module")
def workout_planner(config, jellyfin_mock, workout_videos_df):
    return WorkoutPlanner(
        app_config=config.plan_workouts,
        jellyfin=jellyfin_mock,
        workout_videos=workout_videos_df,
    )


@pytest.fixture(scope="module")
def gsheets_helper(config):
    return GsheetsHelper(config.gsheets)


@pytest.mark.gsheets
class TestLoadLastPlan:
    @staticmethod
    def test_works_as_expected(workout_planner, gsheets_helper, config):
        workbook = gsheets_helper.get_workbook(
            workbook_name=workout_planner.app_config.gsheets.workbook,
        )
        workout_planner._load_weekly_plan(workbook=workbook)
