import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import interp1d
from scipy.optimize import minimize
from scipy.optimize import differential_evolution

iters = 2

def parse_logfile(filename):

    time, spec1, spec2, spec3 = [], [], [], []

    with open(filename, 'r') as f:
        lines = f.readlines()

    for line in lines:
        if "Time" in line:
            start_index = lines.index(line) + 1
            break

    for line in lines[start_index:]:
        if not line.split()[0].replace('.','',1).isdigit():  # Stop parsing when line does not start with a number
            break

        data = line.split()
        time.append(float(data[0]))  # Convert the first entry (Time) to float
        spec1.append(float(data[6]))  # Convert the spec1 quantity to float (7th column in your log)
        spec2.append(float(data[7]))  # Convert the spec2 quantity to float (8th column in your log)
        spec3.append(float(data[8]))

    return time, spec1, spec2, spec3

def interpolate_to_common_time(time, spec, common_time):
    interpolation_function = interp1d(time, spec, fill_value="extrapolate")
    return interpolation_function(common_time)

# choose common time points as uniform timesteps from the minimum to the maximum time point across all runs
min_time = min([min(parse_logfile('log{}.spparks'.format(seed))[0]) for seed in range(1, iters)])
max_time = max([max(parse_logfile('log{}.spparks'.format(seed))[0]) for seed in range(1, iters)])
common_time = np.linspace(min_time, max_time, 10000)  # adjust number of points to change the granularity of the timesteps
# initialize arrays for averages

# Initialize arrays
spec1_avg = np.zeros_like(common_time)
spec2_avg = np.zeros_like(common_time)
spec3_avg = np.zeros_like(common_time)
spec3_finals = []

for seed in range(1, iters):
    time, spec1, spec2, spec3 = parse_logfile('log{}.spparks'.format(seed))
    total_population = np.array(spec1)[0] + np.array(spec2)[0] + np.array(spec3)[0]
    spec1 = interpolate_to_common_time(time, np.array(spec1)/total_population, common_time)
    spec2 = interpolate_to_common_time(time, np.array(spec2)/total_population, common_time)
    spec3 = interpolate_to_common_time(time, np.array(spec3)/total_population, common_time)
    spec3_finals.append(spec3[-1])

# Compute Q1, Q3, IQR, and lower and upper bounds for outliers
q1 = np.percentile(spec3_finals, 25)
q3 = np.percentile(spec3_finals, 75)
iqr = q3 - q1
lower_bound = q1 - 1.5 * iqr
upper_bound = q3 + 1.5 * iqr

# Exclude outliers
count = 0  # counter to track number of seeds included in average

for seed in range(1, iters):
    time, spec1, spec2, spec3 = parse_logfile('log{}.spparks'.format(seed))
    total_population = np.array(spec1)[0] + np.array(spec2)[0] + np.array(spec3)[0]
    spec1 = interpolate_to_common_time(time, np.array(spec1)/total_population, common_time)
    spec2 = interpolate_to_common_time(time, np.array(spec2)/total_population, common_time)
    spec3 = interpolate_to_common_time(time, np.array(spec3)/total_population, common_time)

    if True:
    #if lower_bound <= spec3[-1] <= upper_bound and spec3[-1] >= 0.02:
        spec1_avg += spec1
        spec2_avg += spec2
        spec3_avg += spec3
        count += 1
        plt.plot(common_time, spec1, 'o', color = '#8080FF', alpha=0.002, markersize=1)
        plt.plot(common_time, spec2, 'o', color = '#FF8080', alpha=0.002, markersize=1)
        plt.plot(common_time, spec3, 'o', color = '#80FF80', alpha=0.002, markersize=1)

spec1_avg /= count
spec2_avg /= count
spec3_avg /= count

#for appending with different diffusion rate
def append_to_file(filename, text):
    with open(filename, 'a') as f:
        f.write(text + '\n')

# Define system of ODEs
def deriv(y, t, b, f):
    S, I, R = y
    dSdt = -b * S * I
    dIdt = b * S * I - f * I
    dRdt = f * I
    return dSdt, dIdt, dRdt

# Define RK4 method
def rk4(func, y0, t, args=()):
    dt = t[1] - t[0]
    y = np.zeros((len(t), len(y0)))
    y[0] = y0
    for i in range(len(t) - 1):
        k1 = np.array(func(y[i], t[i], *args))
        k2 = np.array(func(y[i] + dt * k1 / 2., t[i] + dt / 2., *args))
        k3 = np.array(func(y[i] + dt * k2 / 2., t[i] + dt / 2., *args))
        k4 = np.array(func(y[i] + dt * k3, t[i] + dt, *args))
        y[i + 1] = y[i] + dt * 1 / 6. * (k1 + 2 * k2 + 2 * k3 + k4)
    return y
# Define the objective function
def objective(params):
    b, f = params
    y0 = [spec1_avg[0], spec2_avg[0], spec3_avg[0]]
    sol = rk4(deriv, y0, common_time, args=(b, f))
    #Mean Squared Error
    mse = np.mean((sol[:, 0] - spec1_avg) ** 2 + ((sol[:, 1] - spec2_avg) ** 2) + (sol[:, 2] - spec3_avg) ** 2)
    return mse

# Optimize
#initial_guess = [0.6, 0.3]
#solution = minimize(objective, initial_guess, method='Nelder-Mead', options={'xatol': 1e-8, 'disp': True})
#b, f = solution.x
bounds = [(0, 1.2), (0, 1)]
result = differential_evolution(objective, bounds)
b, k = result.x
print("Optimized parameters: b = ", b, ", f = ", k)

# Plot the optimized solution
y0 = [spec1_avg[0], spec2_avg[0], spec3_avg[0]]
sol = rk4(deriv, y0, common_time, args=(b, k))
plt.plot(common_time, sol[:, 0], 'b--', label='ODE S(t)')
plt.plot(common_time, sol[:, 1], 'r--', label='ODE I(t)')
plt.plot(common_time, sol[:, 2], 'g--',  label='ODE R(t)')

s_inf = spec1_avg[-1]
print(s_inf)
c = np.log(s_inf)/(s_inf-1)
print(c)
k_2 = 0.07142857142
b_2 = c * k_2
print("Calculated parameters: c = ", c, ", b = ", b_2)
sol_2 = rk4(deriv, y0, common_time, args=(b_2, k_2))
plt.plot(common_time, sol_2[:, 0], 'b:', label='lnf S(t)')
plt.plot(common_time, sol_2[:, 1], 'r:', label='inf I(t)')
plt.plot(common_time, sol_2[:, 2], 'g:', label='inf R(t)')

append_to_file('diffrate.txt', str(b)+" "+str(k)+" "+str(b_2) + " " +str(k_2))


plt.plot(common_time, spec1_avg, 'b-', label='Average Susceptible')
plt.plot(common_time, spec2_avg, 'r-', label='Average Infected')
plt.plot(common_time, spec3_avg, 'g-', label='Average Recovered')
plt.legend(fontsize = 15)
plt.xlabel("Days", fontsize=21)
plt.ylabel("Proportion of Population", fontsize=21)
plt.title("SIR graph when b = 0.5, k = 1/14", fontsize=25)

# Increasing the size of the legend and the ticks
#plt.legend(fontsize=14)
plt.xticks(fontsize=20)
plt.yticks(fontsize=20)

#with open('diffrate.txt', 'r') as file:
#    last_line = file.readlines()[-2].strip()
#plt.savefig("a_graph{}.png".format(int(float(last_line))))
plt.show()
#plt.close('all')
