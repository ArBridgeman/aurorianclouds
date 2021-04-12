import re

FRACTION_PATTERN = r"^(\d*)\s*(\d+)\/(\d+)"
HTML_FRACTIONS = {"½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4"}


def convert_html_to_fraction(ingredient_line):
    tmp_line = ingredient_line
    for html_fraction, str_fraction in HTML_FRACTIONS.items():
        tmp_line = re.sub(html_fraction, str_fraction, tmp_line)
    return tmp_line


def reduce_fraction_to_decimal(match):
    whole_number = 0
    if match.group(1) != "":
        whole_number = float(match.group(1))
    fraction = int(match.group(2)) / int(match.group(3))
    return "{:.2g}".format(whole_number + fraction)


def switch_fraction_to_decimal(ingredient_line):
    return re.sub(FRACTION_PATTERN, reduce_fraction_to_decimal, ingredient_line)


def standardize_unit_values(ingredient_line):
    str_ingredient_line = convert_html_to_fraction(ingredient_line)
    return switch_fraction_to_decimal(str_ingredient_line)
