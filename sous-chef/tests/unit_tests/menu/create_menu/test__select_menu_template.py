import pytest
from sous_chef.menu.create_menu.models import Season


class TestMenuTemplates:
    @staticmethod
    @pytest.mark.parametrize("menu_number", [1, 12])
    def test__check_menu_template_number_expected_passes(
        menu_templates, menu_number
    ):
        menu_templates._check_menu_template_number(menu_number)

    @staticmethod
    @pytest.mark.parametrize(
        "menu_number,error_message",
        [
            (None, "template menu number (None) not an int"),
            (1.2, "template menu number (1.2) not an int"),
            ("a", "template menu number (a) not an int"),
        ],
    )
    def test__check_menu_template_number_not_integer_raise_value_error(
        menu_templates, menu_number, error_message
    ):
        with pytest.raises(ValueError) as error:
            menu_templates._check_menu_template_number(menu_number)
        assert str(error.value) == error_message

    @staticmethod
    def test__check_menu_template_number_not_in_all_menus_raise_value_error(
        menu_templates,
    ):
        with pytest.raises(ValueError) as error:
            menu_templates._check_menu_template_number(100)
        assert str(error.value) == "template menu number (100) is not found"

    @staticmethod
    @pytest.mark.parametrize("season", Season.value_list())
    def test__check_season_expected_passes(menu_templates, season):
        menu_templates._check_season(season)

    @staticmethod
    @pytest.mark.parametrize("season", ["not-a-season"])
    def test__check_season_not_allowed_values_raise_value_error(
        menu_templates, season
    ):
        with pytest.raises(ValueError) as error:
            menu_templates._check_season(season)
        assert "season" in str(error.value)

    @staticmethod
    def test_load_menu_template(menu_templates, menu_config):
        # ensure that some rows are not unique & multiple seasons
        assert menu_templates.all_menus_df.shape[0] == 20
        assert menu_templates.all_menus_df.menu.nunique() == 14
        assert menu_templates.all_menus_df.season.nunique() == len(
            Season.value_list()
        )

        mask_menu = menu_templates.all_menus_df.menu.isin(
            [menu_config.fixed.basic_number, menu_config.fixed.menu_number]
        )
        mask_season = menu_templates.all_menus_df.season.isin(
            [menu_config.fixed.selected_season, Season.any.value]
        )
        masks = mask_menu & mask_season
        # menu selection > than when season also included
        assert sum(mask_menu) > sum(masks)

        result = menu_templates.load_menu_template()
        # from basic + 2, 0_any + 4_fall
        assert result.shape[0] == sum(masks)

    @staticmethod
    def test_select_upcoming_menus(menu_templates):
        num_weeks = 4
        result = menu_templates.select_upcoming_menus(
            num_weeks_in_future=num_weeks
        )
        assert len(result.menu.unique()) == num_weeks

    @staticmethod
    def test_select_upcoming_menus_start_from_min_when_over(
        menu_templates, menu_config
    ):
        menu_config.fixed.menu_number = 13
        num_weeks = 4
        result = menu_templates.select_upcoming_menus(
            num_weeks_in_future=num_weeks
        )
        assert len(result.menu.unique()) == num_weeks

    @staticmethod
    @pytest.mark.parametrize("num_weeks", [None, 1.2, "a", 0])
    def test_select_upcoming_menus_num_weeks_unexpected_value(
        menu_templates, num_weeks
    ):
        with pytest.raises(ValueError) as error:
            menu_templates.select_upcoming_menus(num_weeks_in_future=num_weeks)
        assert (
            str(error.value) == "fixed.already_in_future_menus.num_weeks "
            f"({num_weeks}) must be int>0"
        )
