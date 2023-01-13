from tests.util import assert_equal_series


class TestMenuHistory:
    @staticmethod
    def test_get_history_from(mock_menu_history):
        assert_equal_series(
            mock_menu_history.get_history_from(days_ago=7).squeeze(),
            mock_menu_history.dataframe.loc[0],
        )
