from typing import List

import pytest
from jellyfin_helpers.workout_plan.get_workouts import TagExtractor
from jellyfin_helpers.workout_plan.models import Difficulty


class TestGetDifficultyFromTags:
    @staticmethod
    @pytest.mark.parametrize(
        "tags,expectation",
        [
            pytest.param([], Difficulty.normal, id="no_difficulty_tag"),
            pytest.param(
                ["difficulty/minus"],
                Difficulty.minus,
                id="minus_difficulty_tag",
            ),
            pytest.param(
                ["difficulty/plus"], Difficulty.plus, id="plus_difficulty_tag"
            ),
            pytest.param(
                ["difficulty/minus", "random"],
                Difficulty.minus,
                id="more_than_one_tag",
            ),
        ],
    )
    def test_works_as_expected(tags: List[str], expectation: Difficulty):
        result = TagExtractor._get_difficulty_from_tags(tags)
        assert result == (expectation.name, expectation.value)

    @staticmethod
    def test_more_than_one_tag_raises_exception():
        with pytest.raises(ValueError):
            TagExtractor._get_difficulty_from_tags(
                ["difficulty/minus", "difficulty/plus"]
            )


class TestGetRatingFromTags:
    @staticmethod
    @pytest.mark.parametrize(
        "tags,expectation",
        [
            pytest.param([], 3.0, id="no_rating_tag"),
            pytest.param(["stars/2.5"], 2.5, id="rating_float_tag"),
            pytest.param(["stars/4"], 4, id="rating_int_tag"),
            pytest.param(
                ["stars/4", "random"],
                4,
                id="more_than_one_tag",
            ),
        ],
    )
    def test_works_as_expected(tags: List[str], expectation):
        assert TagExtractor._get_rating_from_tags(tags) == expectation

    @staticmethod
    def test_more_than_one_tag_raises_exception():
        with pytest.raises(ValueError):
            TagExtractor._get_rating_from_tags(["stars/4", "stars/2.5"])


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
    def test_works_as_expected(tags: List[str], expectation):
        assert TagExtractor._get_tools_from_tag(tags) == expectation


class TestTagExtractor:
    @staticmethod
    @pytest.mark.parametrize(
        "tags,exp_difficulty, exp_rating, exp_tools",
        [
            pytest.param([], Difficulty.normal, 3.0, "", id="use_default_tags"),
            pytest.param(
                ["tool/has-weights"],
                Difficulty.normal,
                3.0,
                "has-weights",
                id="one_tool_tag",
            ),
            pytest.param(
                ["difficulty/plus"],
                Difficulty.plus,
                3.0,
                "",
                id="plus_difficulty_tag",
            ),
            pytest.param(
                ["stars/4"], Difficulty.normal, 4.0, "", id="rating_tag"
            ),
            pytest.param(
                ["difficulty/minus", "stars/4", "tool/has-weights"],
                Difficulty.minus,
                4.0,
                "has-weights",
                id="all_tags",
            ),
        ],
    )
    def test_works_as_expected(
        tags: List[str],
        exp_difficulty: Difficulty,
        exp_rating: float,
        exp_tools: str,
    ):
        assert TagExtractor.extract_tags(tags) == (
            exp_difficulty.name,
            exp_difficulty.value,
            exp_rating,
            exp_tools,
        )

    @staticmethod
    @pytest.mark.parametrize("tag", [1, "1234", True])
    def test_raise_error_if_not_list(tag):
        with pytest.raises(ValueError):
            TagExtractor.extract_tags(tag)
