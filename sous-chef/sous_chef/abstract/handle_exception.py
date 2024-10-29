from dataclasses import dataclass, field
from typing import Callable, List, Tuple

from omegaconf import DictConfig
from sous_chef.abstract.extended_enum import ExtendedEnum


@dataclass
class BaseWithExceptionHandling:
    # needed since dataclass predetermines the kwarg order
    record_exception: List = field(default=None, init=False)
    tuple_log_exception: Tuple = field(default=(), init=False)
    tuple_skip_exception: Tuple = field(default=(), init=False)

    def set_tuple_log_and_skip_exception_from_config(
        self, config_errors: DictConfig, exception_mapper: ExtendedEnum
    ):
        tuple_log_exception = []
        tuple_skip_exception = []
        for error, what_to_do in config_errors.items():
            if what_to_do == "raise":
                continue
            exception = exception_mapper[error].value
            if what_to_do == "log":
                tuple_log_exception.append(exception)
            elif what_to_do == "skip":
                tuple_skip_exception.append(exception)
            else:
                raise ValueError(f"{what_to_do} not defined")

        self.tuple_log_exception = tuple(tuple_log_exception)
        self.tuple_skip_exception = tuple(tuple_skip_exception)

    class ExceptionHandler:
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
