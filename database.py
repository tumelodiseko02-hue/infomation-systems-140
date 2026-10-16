import sqlite3
from contextlib import closing

DATABASE = "agritrial.db"

REQUIRED = ["site", "trial_date", "crop", "treatment_group", "observer"]
OPTIONAL = [
    "plant_height", "leaf_count", "fresh_weight", "dry_weight",
    "chlorophyll", "root_length", "yield_value",
    "ph", "ec", "dissolved_oxygen", "temperature",
    "humidity", "nitrate", "phosphate",
]


def create_database():
    with closing(sqlite3.connect(DATABASE)) as conn, conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trial_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site TEXT NOT NULL,
                trial_date TEXT NOT NULL,
                crop TEXT NOT NULL,
                treatment_group TEXT NOT NULL,
                observer TEXT NOT NULL,
                plant_height REAL, leaf_count INTEGER,
                fresh_weight REAL, dry_weight REAL,
                chlorophyll REAL, root_length REAL, yield_value REAL,
                ph REAL, ec REAL, dissolved_oxygen REAL,
                temperature REAL, humidity REAL,
                nitrate REAL, phosphate REAL
            )
        """)


def save_trial(data):
    row = {k: data[k] for k in REQUIRED}
    row.update({k: data.get(k) for k in OPTIONAL})
    columns = ", ".join(row)
    placeholders = ", ".join(f":{k}" for k in row)
    with closing(sqlite3.connect(DATABASE)) as conn, conn:
        cur = conn.execute(
            f"INSERT INTO trial_data ({columns}) VALUES ({placeholders})", row
        )
        return cur.lastrowid


if __name__ == "__main__":
    create_database()
    samples = [
        dict(site="Site A", trial_date="2026-10-01", crop="Lettuce", treatment_group="Control", observer="Observer 1",
             plant_height=12.4, leaf_count=9, fresh_weight=45.2, dry_weight=3.1, chlorophyll=38.5, root_length=10.2,
             yield_value=210.0, ph=6.1, ec=1.8, dissolved_oxygen=7.2, temperature=22.5, humidity=65.0, nitrate=150.0, phosphate=40.0),
        dict(site="Site A", trial_date="2026-10-01", crop="Lettuce", treatment_group="Treatment 1", observer="Observer 1",
             plant_height=14.1, leaf_count=11, fresh_weight=52.8, dry_weight=3.6, chlorophyll=41.2, root_length=11.5,
             yield_value=245.0, ph=6.0, ec=2.0, dissolved_oxygen=7.0, temperature=22.8, humidity=64.0, nitrate=165.0, phosphate=45.0),
        dict(site="Site B", trial_date="2026-10-02", crop="Tomato", treatment_group="Control", observer="Observer 2",
             plant_height=35.6, leaf_count=18, fresh_weight=180.5, dry_weight=14.2, chlorophyll=44.0, root_length=22.3,
             yield_value=820.0, ph=6.4, ec=2.4, dissolved_oxygen=6.8, temperature=24.1, humidity=70.0, nitrate=190.0, phosphate=55.0),
        dict(site="Site B", trial_date="2026-10-02", crop="Tomato", treatment_group="Treatment 1", observer="Observer 2",
             plant_height=38.2, leaf_count=20, fresh_weight=198.3, dry_weight=15.9, chlorophyll=46.7, root_length=24.0,
             yield_value=905.0, ph=6.3, ec=2.5, dissolved_oxygen=6.9, temperature=24.0, humidity=69.0, nitrate=205.0, phosphate=60.0),
        dict(site="Site C", trial_date="2026-10-03", crop="Basil", treatment_group="Control", observer="Observer 3"),
    ]
    for s in samples:
        save_trial(s)
    print("agritrial.db created with", len(samples), "sample rows")
    

    
    