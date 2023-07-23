from dataclasses import dataclass
from pathlib import Path

from sous_chef.menu.create_menu._for_todoist import MenuForTodoist
from sous_chef.menu.create_menu._from_fixed_template import (
    MenuFromFixedTemplate,
)
from structlog import get_logger

ABS_FILE_PATH = Path(__file__).absolute().parent
FILE_LOGGER = get_logger(__name__)


@dataclass
class Menu(MenuForTodoist, MenuFromFixedTemplate):
    pass
