from dataclasses import dataclass
from typing import Dict

import pytest
from sous_chef.abstract.handle_exception import BaseWithExceptionHandling

from utilities.extended_enum import ExtendedEnum

CUSTOM_MESSAGE = "Dummy Exception Custom Message"


class DummyException(Exception):
    pass


class MapErrorToException(ExtendedEnum):
    dummy_error = DummyException


@dataclass
class DummyClass(BaseWithExceptionHandling):
    config_error: Dict

    def __post_init__(self):
        self.set_tuple_log_and_skip_exception_from_config(
            config_errors=self.config_error,
            exception_mapper=MapErrorToException,
        )
        self.record_exception = []

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def run_raise_error(self):
        raise DummyException(CUSTOM_MESSAGE)


class TestBaseWithExceptionHandling:
    @staticmethod
    def _create_config_error(what_to_do: str):
        return {"dummy_error": what_to_do}

    def test_dummy_raise_error(self):
        config_error = self._create_config_error(what_to_do="raise")
        dummy_class = DummyClass(config_error=config_error)

        with pytest.raises(DummyException):
            dummy_class.run_raise_error()
        assert dummy_class.record_exception == []

    def test_dummy_log_error(self):
        config_error = self._create_config_error(what_to_do="log")
        dummy_class = DummyClass(config_error=config_error)
        dummy_class.run_raise_error()
        assert dummy_class.record_exception == [CUSTOM_MESSAGE]

    def test_dummy_skip_error(self):
        config_error = self._create_config_error(what_to_do="skip")
        dummy_class = DummyClass(config_error=config_error)
        dummy_class.run_raise_error()
        assert dummy_class.record_exception == []

    def test_dummy_unknown_what_to_do(self):
        config_error = self._create_config_error(what_to_do="unknown")
        with pytest.raises(ValueError):
            dummy_class = DummyClass(config_error=config_error)
            assert dummy_class.record_exception == []
