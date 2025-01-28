from datetime import datetime
from pathlib import Path

import hydra
import numpy as np
from omegaconf import DictConfig
from sous_chef.menu.create_menu.create_menu import Menu
from sous_chef.rtk.read_write_rtk import RtkService
from structlog import get_logger

ABS_FILE_PATH = Path(__file__).absolute().parent
FILE_LOGGER = get_logger(__name__)


def run_menu(config: DictConfig):
    # TODO couple inherently with recipe book service
    # unzip latest recipe versions
    rtk_service = RtkService(config.rtk)
    rtk_service.unzip()

    menu = Menu(config=config)
    if config.menu.create_menu.input_method == "fixed":
        return menu.fill_menu_template_and_save()
    elif config.menu.create_menu.input_method == "final":
        return menu.finalize_menu_to_external_services()


@hydra.main(
    config_path="../../config/", config_name="menu_main", version_base=None
)
def main(config: DictConfig):
    if config.random.seed is None:
        config.random.seed = datetime.now().timestamp()
    config.random.seed = int(config.random.seed)
    # globally set random seed for numpy based calls
    np.random.seed(config.random.seed)

    try:
        run_menu(config)
    except Exception as e:
        raise e
    finally:
        FILE_LOGGER.info(
            f"Use random seed {config.random.seed} to reproduce this run!"
        )


if __name__ == "__main__":
    main()
