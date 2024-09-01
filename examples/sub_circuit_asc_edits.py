import os
from spicelib.editor.asc_editor import AscEditor

E = AscEditor('testfiles\\top_circuit.asc')
print(E.get_components())
print(E.get_components('R'))
print(E.get_subcircuit('X1').get_components())
E.set_component_value("X1:L1", 2e-6)
print(E['R1'].value)
print("Setting R1 to 10k")
E['R1'].value = 11
print("Setting parameter I1 1.23k")
E.set_parameter("V1", "PULSE(0 1 1n 1n 1n {0.5/freq} {1/freq} 10)")
print(E.get_parameter('V1'))
print("Setting frequency to 1MHz")
E.set_parameters(freq=1E6)
print("Setting XX1:L1 to 1µH")
E["X1:L1"].value = '1µH'
print("Setting XX1:C1 to 22nF")
E["X1:C1"].value = 22e-9
print("Setting XX1:C2 to 120nF")
E["X1:C2"].value = '120n'
print(E["X1:C1"].value)
print(E.get_component_floatvalue("X1:C2"))
print(E["X1:L1"].value)
print(E["R2"].value_str)
E.set_parameters(
    test_exiting_param_set1=24,
    test_exiting_param_set2=25,
    test_exiting_param_set3=26,
    test_exiting_param_set4=27,
    test_add_parameter=34.45, )
S = E.get_subcircuit('X1')
S.asc_file_path = "testfiles\\subcircuit_edit.asc" # Only for test purposes
E.save_netlist("testfiles\\top_circuit_edit.asc")
