import re

action_regex = re.compile(r"\w+ed")

# 1 lemon, zested
# lemon juice; not freshly squeezed lemon juice
# soya sauce -> soy sauce
# check cases to make sure no extra spaces and spaces added (sometimes no space between # and unit)
special_phrases = {"finely chopped": "diced",
                   "coarsely chopped": "chopped",
                   "freshly chopped": "chopped",
                   "thinly chopped": "diced",
                   "roughly chopped": "chopped",
                   "cracked": "",
                   "freshly cracked": "",
                   "finely crushed": "crushed",
                   "slightly crushed": "crushed",
                   "finely diced": "minced",
                   "roughly diced": "chopped",
                   "coarsely grated": "shredded",
                   "finely grated": "grated",
                   "freshly grated": "grated",
                   "freshly grounded": "",
                   "thinly julienned": "julienned",
                   "lightly mashed": "mashed",
                   "finely minced": "minced",
                   "freshly minced": "minced",
                   "lightly packed": "",
                   "loosely packed": "",
                   "finely shredded": "grated",
                   "finely sliced": "julienned",
                   "freshly shredded": "shredded",
                   "thickly sliced": "sliced",
                   "thinly sliced": "julienned",
                   "freshly squeezed": "",
                   "fully thawed": "thawed",
                   "finely zested": "zested",
                   }

action_words = ['baked', 'hulled', 'blended', 'boiled', 'chilled', 'chopped', 'cooked', 'cooled', 'cored', 'crumbled',
                'cubed', 'diced', 'divided', 'drained', 'filtered', 'grated', 'grilled', 'halved', 'julienned',
                'mashed', 'melted', 'microwaved', 'minced', 'packed', 'peeled', 'pureed', 'quartered', 'rinsed',
                'scrambled', 'separated', 'shredded', 'sifted', 'sliced', 'smashed', 'softened', 'squeezed',
                'steamed', 'thawed', 'toasted', 'trimmed', 'washed', 'whipped', 'zested']

""" examples
1 shallot, thinly sliced
0.25 cup whole roasted almonds (roughly chopped)
1 avocado, halved, seeded, peeled and sliced
0.25 cup chopped nuts of choice (optional)
1.5 cups grated Parmesan
2 cm long fresh ginger root, peeled and roughly diced (about 1 tablespoon grated)
0.5 pound lamb (or beef or chicken), chopped into 1/2-inch pieces
"""


def replace_adverb_verb_usage(ingredient_line):
    std_ingredient_line = ingredient_line
    for key_old, value_new in special_phrases.items():
        std_ingredient_line = re.sub(key_old, value_new, std_ingredient_line.lower())
    return std_ingredient_line


def relocate_action(ingredient_line):
    std_ingredient_line = replace_adverb_verb_usage(ingredient_line)
    results = action_regex.finditer(std_ingredient_line.lower())
    action_results = []
    for result in results:
        word = result.group()
        if word in action_words:
            action_results.append(word)
    if len(action_results) > 0:
        print(ingredient_line)
        print(", ".join(action_results))
    # print(result.group())
    # print(result.span())
    # print(len(ingredient_line))
    # results = action_regex.findall(ingredient_line)
    # print(results.group())
    # test_results = [result in action_words for result in results]
    # if any(test_results):
    #     print(ingredient_line)
