class TestCreateMenu:
    pass
    # @staticmethod
    # def test_menu_menu_template_fails_for_record_exception(
    #         menu, menu_config, mock_recipe_book, capsys
    # ):
    #     menu_config.fixed.menu_number = 0
    #     menu.tuple_log_exception = (RecipeNotFoundError,)
    #
    #     # derived exception MenuIncompleteError
    #     with pytest.raises(Exception) as error:
    #         menu.fill_menu_template()
    #
    #     assert (
    #             str(error.value)
    #             == "[menu had errors] will not send to finalize until fixed"
    #     )
    #     assert (
    #             "[recipe not found] recipe=dummy search_results=[dummy]"
    #             in capsys.readouterr().out
    #     )
