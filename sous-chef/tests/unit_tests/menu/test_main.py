from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from hydra import compose, initialize
from sous_chef.menu.create_menu.exceptions import MenuIncompleteError
from sous_chef.menu.main import main


@pytest.fixture
def menu_error():
    menu_error = Mock()
    menu_error.side_effect = MenuIncompleteError("menu incomplete")
    return menu_error


class TestMain:
    @staticmethod
    def test_main_raises_error_and_prints_seed_default(menu_error, log):
        with initialize(version_base=None, config_path="../../../config"):
            config = compose(config_name="menu_main")
            with patch("sous_chef.menu.main.run_menu", menu_error):
                with pytest.raises(Exception) as error:
                    main(config)

                assert str(error.value) == "[menu had errors] menu incomplete"
                assert (
                    log.events[0]["event"]
                    == f"Use random seed {int(datetime.now().timestamp())} "
                    f"to reproduce this run!"
                )

    @staticmethod
    @pytest.mark.parametrize("seed", [42, 1337])
    def test_main_raises_error_and_prints_seed_custom_seed(
        menu_error, seed, log
    ):
        with initialize(version_base=None, config_path="../../../config"):
            config = compose(config_name="menu_main")
            config.random.seed = seed
            with patch("sous_chef.menu.main.run_menu", menu_error):
                with pytest.raises(Exception) as error:
                    main(config)

                assert str(error.value) == "[menu had errors] menu incomplete"
                assert (
                    log.events[0]["event"]
                    == f"Use random seed {seed} to reproduce this run!"
                )
