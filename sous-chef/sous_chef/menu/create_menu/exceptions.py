from dataclasses import dataclass


@dataclass
class MenuIncompleteError(Exception):
    custom_message: str
    message: str = "[menu had errors]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message} {self.custom_message}"


@dataclass
class MenuConfigError(Exception):
    custom_message: str
    message: str = "[menu config error]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message} {self.custom_message}"


@dataclass
class MenuQualityError(Exception):
    error_text: str
    recipe_title: str
    message: str = "[menu quality]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return (
            f"{self.message} recipe={self.recipe_title} error={self.error_text}"
        )


@dataclass
class MenuFutureError(Exception):
    error_text: str
    recipe_title: str
    message: str = "[future menu]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return (
            f"{self.message} recipe={self.recipe_title} error={self.error_text}"
        )
