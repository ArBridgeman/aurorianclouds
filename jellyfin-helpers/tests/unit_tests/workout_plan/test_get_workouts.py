import pytest
from jellyfin_helpers.workout_plan.get_workouts import WorkoutVideos


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
