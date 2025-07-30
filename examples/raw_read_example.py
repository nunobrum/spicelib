from spicelib import RawRead

from matplotlib import pyplot as plt

# read a raw file that has only 1 data set/plot in it, but has multiple steps
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

# read a raw file that has multiple data sets/plots in it
raw = RawRead("./testfiles/noise_multi.bin.raw")
print(raw.get_plot_names())            # names of all the plots in the file
print(raw.get_trace_names())           # names of all the traces of the first plot in the file
print(raw.plots[0].get_trace_names())  # same as above
print(raw.plots[1].get_trace_names())  # names of all the traces of the second plot in the file

# Gets the frequency axis of the first plot (same as raw.plots[0].get_trace('frequency'))
x = raw.get_trace('frequency')  # could have used raw.get_axis() as well here
y = raw.get_trace('onoise_spectrum')
plt.plot(x.get_wave(), y.get_wave(), label='noise spectrum')
plt.xlabel('Frequency (Hz)')
plt.ylabel('Noise Spectrum (V/√Hz)')
plt.yscale('log')
plt.xscale('log')
plt.legend()  # order a legend
plt.show()

total = raw.plots[1].get_trace('v(onoise_total)')
print(f"Total Integral noise: {total.get_wave()[0]} V") 
