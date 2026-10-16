import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

# ---------- 1. Find and load the data ----------
# Looks for the CSV in the same folder as this script, then in Downloads.
CSV_NAME = "AgriTrial_Data_Canola.csv"
script_folder = os.path.dirname(os.path.abspath(__file__))
downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")

csv_path = None
for folder in (script_folder, downloads_folder):
    candidate = os.path.join(folder, CSV_NAME)
    if os.path.exists(candidate):
        csv_path = candidate
        break

if csv_path is None:
    print(f"Could not find {CSV_NAME}.")
    print("Put the CSV in this folder:", script_folder)
    print("CSV files currently in that folder:",
          [f for f in os.listdir(script_folder) if f.lower().endswith(".csv")])
    raise SystemExit

df = pd.read_csv(csv_path)

# ---------- 2. Choose the two measurements ----------
column = "Mg"            # which measurement to analyse
group_a = "Control"      # first group
group_b = "Combined"     # second group

data_a = df.loc[df["Block"] == group_a, column]
data_b = df.loc[df["Block"] == group_b, column]

# ---------- 3. Calculate mean and 95% confidence interval ----------
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

# ---------- 4. Plot ----------
errors = [
    [mean_a - lower_limit_a, mean_b - lower_limit_b],   # distance down from each mean
    [upper_limit_a - mean_a, upper_limit_b - mean_b],   # distance up from each mean
]

plt.errorbar([group_a, group_b], [mean_a, mean_b], yerr=errors,
             fmt="s", capsize=6, color="green")
plt.ylabel("Magnesium (Mg) concentration")
plt.title("Magnesium Concentration with 95% Confidence Interval")
plt.xlim(-1, 2)
plt.show()
