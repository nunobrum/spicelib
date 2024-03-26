import os
from spicelib.editor import SpiceEditor

try:
    import rich
except ImportError:
    import pip
    pip.main(["install", "rich"])


E = SpiceEditor('testfiles\\edit_test.net')
print("Circuit Nodes", E.get_all_nodes())
E.add_library_search_paths([r"C:\SVN\Electronic_Libraries\LTSpice\lib"])
E.set_element_model("XU2", 324)
E.set_component_value("XU1:XDUT:R77", 200)
print(E.get_component_value('R1'))
print("Setting R1 to 10k")
E.set_component_value('R1', 10000)
print("Setting parameter I1 1.23k")
E.set_parameter("I1", "1.23k")
print(E.get_parameter('I1'))
print("Setting {freq*(10/5.0})")
E.set_parameters(I2="{freq*(10/5.0})")
print(E.get_parameter('I2'))
print(E.get_components())
print(E.get_components('RC'))
print("Setting C1 to 1µF")
E.set_component_value("C1", '1µF')
print("Setting C4 to 22nF")
E.set_component_value("C4", 22e-9)
print("Setting C3 to 120nF")
E.set_component_value("C3", '120n')
print(E.get_component_floatvalue("C1"))
print(E.get_component_floatvalue("C3"))
print(E.get_component_floatvalue("C4"))
E.set_parameters(
    test_exiting_param_set1=24,
    test_exiting_param_set2=25,
    test_exiting_param_set3=26,
    test_exiting_param_set4=27,
    test_add_parameter=34.45, )
E.save_netlist("..\\tests\\test_spice_editor.net")