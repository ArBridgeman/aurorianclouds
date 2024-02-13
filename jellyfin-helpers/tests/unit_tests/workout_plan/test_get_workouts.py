from datetime import timedelta

import pytest
from jellyfin_helpers.workout_plan.get_workouts import (
    DEFAULT_TIME,
    WorkoutVideos,
)


class TestGetDurationFromTags:
    @staticmethod
    @pytest.mark.parametrize(
        "tags,expectation",
        [
            pytest.param([], DEFAULT_TIME, id="no_time_tag"),
            pytest.param(
                ["5-10 min"], timedelta(minutes=7.5), id="one_time_tag"
            ),
            pytest.param(
                ["5-10 min", "random"],
                timedelta(minutes=7.5),
                id="more_than_one_tag",
            ),
            pytest.param(
                ["5-10 min", "20-25 min"],
                timedelta(minutes=7.5),
                id="more_than_one_time_tag",
            ),
        ],
    )
    def test_works_as_expected(tags, expectation):
        assert WorkoutVideos.get_duration_from_tags(tags) == expectation


class TestGetToolFromTags:
    @staticmethod
    @pytest.mark.parametrize(
        "tags,expectation",
        [
            pytest.param([], "", id="no_tool_tag"),
            pytest.param(
                ["tool/has-weights"], "has-weights", id="one_tool_tag"
            ),
            pytest.param(
                ["tool/has-weights", "random"],
                "has-weights",
                id="more_than_one_tag",
            ),
            pytest.param(
                ["tool/has-weights", "tool/band"],
                "has-weights, band",
                id="more_than_one_tool_tag",
            ),
        ],
    )
    def test_works_as_expected(tags, expectation):
        assert WorkoutVideos.get_tool_from_tags(tags) == expectation

    @staticmethod
    @pytest.mark.parametrize("tags", [1, "1234", True])
    def test_raise_error_if_not_list(tags):
        with pytest.raises(ValueError):
            WorkoutVideos.get_tool_from_tags(tags)
