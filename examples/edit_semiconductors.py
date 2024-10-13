import spicelib

netlist = spicelib.SpiceEditor("./testfiles/amp3/amp3.net")
print("Before")
l = netlist.get_subcircuit("XOPAMP").get_component_parameters('M00').items()
print(f"XOPAMP:M00 params={l}")
newsettings = {"W": 10E-6}
netlist.get_subcircuit("XOPAMP").set_component_parameters("M00", **newsettings)
# or: netlist.get_subcircuit("XOPAMP").set_component_parameters("M00", W=10E-6)
print("After")
l = netlist.get_subcircuit("XOPAMP").get_component_parameters('M00').items()
print(f"XOPAMP:M00 params={l}")