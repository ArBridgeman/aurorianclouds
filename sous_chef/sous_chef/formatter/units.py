from pint import UnitRegistry

unit_registry = UnitRegistry()
unit_registry.default_format = ".2f"

# custom units
unit_registry.define("ball = 1")
unit_registry.define("can = 1")
unit_registry.define("cube = 1")
unit_registry.define("drop = 1")
unit_registry.define("head = 1")
unit_registry.define("jar = 1")
unit_registry.define("pinch = 1")
unit_registry.define("@alias pinch = pinches")
unit_registry.define("package = 1 =  pkg")
unit_registry.define("packet = 1 = pkt")
unit_registry.define("slice = 1")

custom_list = [
    unit_registry.ball,
    unit_registry.can,
    unit_registry.cube,
    unit_registry.drop,
    unit_registry.head,
    unit_registry.jar,
    unit_registry.pinch,
    unit_registry.slice,
]

custom_list_abbr = [unit_registry.package, unit_registry.packet]

metric = [
    unit_registry.millimeter,
    unit_registry.centimeter,
    unit_registry.gram,
    unit_registry.kilogram,
    unit_registry.milliliter,
    unit_registry.centiliter,
    unit_registry.liter,
]

empirical = [
    unit_registry.inch,
    unit_registry.ounce,
    unit_registry.pound,
    unit_registry.teaspoon,
    unit_registry.tablespoon,
    unit_registry.pint,
    unit_registry.quart,
    unit_registry.cup,
]

allowed_unit_list = custom_list + custom_list_abbr + metric + empirical

not_abbreviated = custom_list + [unit_registry.cup]
