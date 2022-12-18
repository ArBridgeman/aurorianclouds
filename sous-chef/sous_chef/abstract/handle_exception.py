from dataclasses import dataclass, field
from typing import Callable, List, Tuple

from omegaconf import DictConfig
from sous_chef.date.get_due_date import ExtendedEnum
from sous_chef.formatter.ingredient.format_ingredient import (
    BadIngredientError,
    EmptyIngredientError,
    PantrySearchError,
)
from sous_chef.formatter.ingredient.format_line_abstract import LineParsingError
from sous_chef.menu.record_menu_history import MenuHistoryError
from sous_chef.recipe_book.read_recipe_book import RecipeNotFoundError


class MapErrorToException(ExtendedEnum):
    recipe_not_found = RecipeNotFoundError
    recipe_in_recent_menu_history = MenuHistoryError
    ingredient_line_parsing_error = LineParsingError
    no_ingredient_found_in_line = EmptyIngredientError
    pantry_ingredient_not_known = PantrySearchError
    ingredient_marked_as_bad = BadIngredientError


@dataclass
class BaseWithExceptionHandling(object):
    # needed since dataclass predetermines the kwarg order
    record_exception: List = field(default=None, init=False)
    tuple_log_exception: Tuple = field(default=None, init=False)
    tuple_skip_exception: Tuple = field(default=None, init=False)

    def set_tuple_log_and_skip_exception_from_config(
        self, config_errors: DictConfig
    ):
        tuple_log_exception = []
        tuple_skip_exception = []
        for error, what_to_do in config_errors.items():
            if what_to_do == "raise":
                continue
            exception = MapErrorToException[error].value
            if what_to_do == "log":
                tuple_log_exception.append(exception)
            elif what_to_do == "skip":
                tuple_skip_exception.append(error)

        self.tuple_log_exception = tuple(tuple_log_exception)
        self.tuple_skip_exception = tuple(tuple_skip_exception)

    class ExceptionHandler(object):
        @classmethod
        def handle_exception(cls, func: Callable) -> Callable:
            def inner_function(*args, **kwargs):
                class_called = args[0]
                try:
                    return func(*args, **kwargs)
                except class_called.tuple_log_exception as exception:
                    class_called.record_exception.append(str(exception))
                except class_called.tuple_skip_exception:
                    pass

            return inner_function
