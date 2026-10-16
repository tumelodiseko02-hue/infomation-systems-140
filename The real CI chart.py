
import numpy as np

import pandas as pd

import matplotlib.pyplot as plt

from scipy import stats

plt.rcParams["toolbar"] = "None"

df = pd.read_csv("AgriTrial+Data+Canola.csv")

column = "Mg" 

group_a = "Control"

group_b = "Combined"    

data_a = df.loc[df["Block"] == group_a, column]

data_b = df.loc[df["Block"] == group_b, column]

# Calculate mean and 95% confidence interval 
def mean_and_conf_interval(data, confidence=0.95):

    data = np.array(data)

    n = len(data)

    mean = data.mean()

    sem = stats.sem(data)

    lower_limit, upper_limit = stats.t.interval(confidence, n - 1, loc=mean, scale=sem)

    return mean, lower_limit, upper_limit

mean_a, lower_limit_a, upper_limit_a = mean_and_conf_interval(data_a)

mean_b, lower_limit_b, upper_limit_b = mean_and_conf_interval(data_b)

print(f"{group_a}:  mean={mean_a:.2f}, 95% CI=({lower_limit_a:.2f}, {upper_limit_a:.2f})")

print(f"{group_b}: mean={mean_b:.2f}, 95% CI=({lower_limit_b:.2f}, {upper_limit_b:.2f})")

# Draws the Graph
errors = [
    [mean_a - lower_limit_a, mean_b - lower_limit_b],  
    [upper_limit_a - mean_a, upper_limit_b - mean_b],   
]

plt.errorbar([group_a, group_b], [mean_a, mean_b], yerr=errors,
             fmt="s", capsize=6, color="green")

plt.ylabel("Magnesium (Mg) concentration")

plt.title("Magnesium Concentration with 95% Confidence Interval")

plt.xlim(-1, 2)

plt.show()
