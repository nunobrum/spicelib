from spicelib import RawRead

from matplotlib import pyplot as plt

rawfile = RawRead("./testfiles/TRAN - STEP.raw")

print(rawfile.get_trace_names())
print(rawfile.get_raw_property())

IR1 = rawfile.get_trace("I(R1)")
x = rawfile.get_trace('time')  # Gets the time axis
steps = rawfile.get_steps()
for step in range(len(steps)):
    # print(steps[step])
    plt.plot(x.get_wave(step), IR1.get_wave(step), label=steps[step])

plt.legend()  # order a legend
plt.show()
