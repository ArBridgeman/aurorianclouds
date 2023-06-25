from dataclasses import dataclass
from pathlib import Path

from sous_chef.grocery_list.generate_grocery_list._aggregated import (
    GroceryListAggregated,
)
from sous_chef.grocery_list.generate_grocery_list._extract_from_menu import (
    GroceryListExtractedFromMenu,
)
from sous_chef.grocery_list.generate_grocery_list._for_todoist import (
    GroceryListForTodoist,
)
from structlog import get_logger

ABS_FILE_PATH = Path(__file__).absolute().parent
FILE_LOGGER = get_logger(__name__)


@dataclass
class GroceryList(
    GroceryListExtractedFromMenu, GroceryListAggregated, GroceryListForTodoist
):
    pass
