import os
from spicelib.editor.qsch_editor import QschEditor

E = QschEditor('testfiles\\top_circuit.qsch')
# E = QschEditor('testfiles\\TRAN.qsch')
print(E.get_components())
print(E.get_components('R'))
print(E.get_subcircuit('X1').get_components())
# reading component values
for E_comp in E.get_subcircuit('X1').get_components():
    comp_designator = 'X1:' + E_comp
    print(f"X1:{comp_designator} = {E[comp_designator]}")
print("Setting X1:R1 to 100")
E.set_component_value("X1:R1", 100)
print(E['R1'].value)
print("Setting R1 to 10k")
E['R1'].value = 11
print("Setting parameter V1 a pulse ")
E.set_parameter("V1", "PULSE(0 1 1n 1n 1n {0.5/freq} {1/freq} 10)")
E.set_parameters(
    test_exiting_param_set1=24,
    test_exiting_param_set2=25,
    test_exiting_param_set3=26,
    test_exiting_param_set4=27,
    test_add_parameter=34.45, )
S = E.get_subcircuit('X1')
S.asc_file_path = "testfiles\\subcircuit_edit.qsch"  # Only for test purposes
S.write_netlist("testfiles\\subcircuit_qsch.net")
E.save_netlist("testfiles\\top_circuit_edit.qsch")
E.save_netlist("testfiles\\top_circuit_edit_qsch.net")
