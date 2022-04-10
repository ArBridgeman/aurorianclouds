def convert_number_to_str(number, precision=2):
    """
    Returns string of given number with defined amount of significant digits.
    :param number: number to print nicely (int/float)
    :param precision: significant digits to be included
    :return: formatted string
    """
    if isinstance(number, int):
        return f"{number}"
    return "{:g}".format(float("{:.{p}g}".format(number, p=precision)))
