def convert_float_to_str(number, precision=2):
    """
    Returns string from given number with defined amount of significant digits.
    :param number: number to print nicely (int/float)
    :param precision: significant digits to be included
    :return: formatted string
    """
    return "{:g}".format(float("{:.{p}g}".format(number, p=precision)))
