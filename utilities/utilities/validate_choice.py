from utilities.extended_enum import ExtendedEnum

MAX_DEFAULT_ASK = 3


class YesNoChoices(ExtendedEnum):
    yes = "y"
    no = "n"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            value_lower = value.lower()
            for member in cls:
                if member.value.lower() == value_lower:
                    return member
        return None

    @staticmethod
    def ask_yes_no(text: str, debug_mode: bool = False) -> "YesNoChoices":
        if debug_mode:
            return YesNoChoices.no

        response_count = 0
        response = None
        while (
            response not in YesNoChoices.value_list(string_method="lower")
            and response_count < MAX_DEFAULT_ASK
        ):
            response = input(f"\n{text} [y]es, [n]o: ").lower()
            response_count += 1
        return YesNoChoices(response)
