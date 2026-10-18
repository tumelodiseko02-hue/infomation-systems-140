
import random

from auth import AuthDB
from storage import make_storage
from trial_db import SAMPLES, TrialDB

random.seed(42)

# farmer / yield data (farm.db)
store = make_storage()
VILLAGES = ["Mbeya", "Iringa", "Njombe", "Songea"]
CROP_MEANS = {"Maize": 3200, "Sorghum": 1900, "Beans": 1300, "Cassava": 8500}
TREATMENTS = ["Control", "Fertilizer", "Compost"]
BUMP = {"Control": 0.0, "Fertilizer": 0.18, "Compost": 0.08}

farmers = [
    store.find_farmer_by_phone(f"0700000{i:03d}")
    or store.add_farmer({"name": f"Farmer {i}", "phone": f"0700000{i:03d}",
                         "village": random.choice(VILLAGES),
                         "farm_size_ha": round(random.uniform(0.5, 6), 2)})
    for i in range(12)
]
count = 0
for crop, mean in CROP_MEANS.items():
    for _ in range(9):
        t = random.choice(TREATMENTS)
        y = random.gauss(mean * (1 + BUMP[t]), mean * 0.12)
        store.add_trial({
            "farmer_id": random.choice(farmers)["id"], "crop": crop,
            "variety": "Standard", "treatment": t,
            "planting_date": f"2026-0{random.randint(1, 4)}-{random.randint(10, 28)}",
            "yield_kg_per_ha": round(max(y, 50), 1), "notes": "seed data",
        })
        count += 1
print(f"farm data: {len(farmers)} farmers, {count} yield trials ('{store.name}' storage)")

# trial measurements (agritrial.db): your 5 samples + replicates so CIs exist
trials = TrialDB()
for s in SAMPLES:
    trials.save(trials.clean(s)[0])
n = len(SAMPLES)
for group, bump in (("Control", 0.0), ("Treatment 1", 0.15)):
    for _ in range(8):
        trials.save(trials.clean(dict(
            site="Site A", trial_date="2026-10-05", crop="Lettuce", treatment_group=group,
            observer="Observer 1",
            plant_height=round(random.gauss(12.5 * (1 + bump), 1.0), 1),
            fresh_weight=round(random.gauss(45 * (1 + bump), 4.0), 1),
            yield_value=round(random.gauss(210 * (1 + bump), 15.0), 1),
        ))[0])
        n += 1
print(f"trial_data: {n} rows in {trials.path}")

# logins (login.sqlite): AuthDB seeds USERONE/0000 and USERTWO/0001 when empty
print(f"logins: {AuthDB().count()} accounts in login.sqlite (demo users: USERONE/0000, USERTWO/0001)")
