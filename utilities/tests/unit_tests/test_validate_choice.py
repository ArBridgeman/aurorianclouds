from unittest.mock import patch

import pytest

from utilities.validate_choice import MAX_DEFAULT_ASK, YesNoChoices


class TestYesNoChoices:
    @staticmethod
    def test__missing_works_as_expected():
        value = "Y"
        # ensure initial test condition is met
        assert value not in YesNoChoices.value_list("lower")

        assert YesNoChoices(value) == YesNoChoices.yes

    @staticmethod
    @pytest.mark.parametrize("choice", [YesNoChoices.yes, YesNoChoices.no])
    def test_ask_yes_no_works_as_expected(choice: YesNoChoices):
        with patch("builtins.input", side_effect=[choice.value]):
            response = YesNoChoices.ask_yes_no("...do that?")
        assert response == choice

    @staticmethod
    def test_ask_yes_no_terminates_in_error_after_max_calls():
        with pytest.raises(ValueError):
            with patch("builtins.input", side_effect=["b"] * MAX_DEFAULT_ASK):
                YesNoChoices.ask_yes_no("...do that?")

    @staticmethod
    def test_ask_yes_no_debug_mode_works_as_expected():
        assert (
            YesNoChoices.ask_yes_no("...do that?", debug_mode=True)
            == YesNoChoices.no
        )
