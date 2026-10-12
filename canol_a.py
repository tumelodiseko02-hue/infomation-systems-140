
import csv
import sqlite3

conn = sqlite3.connect("canola.sqlite")
cur = conn.cursor()


cur.execute("""
CREATE TABLE IF NOT EXISTS trial_site (
    Year DATE,
    Block TEXT,
    Replicates INTEGER,
    Yield INTEGER,
    "Bio Yield" DECIMAL,
    "pod/plant" DECIMAL,
    "seed/pod" DECIMAL,
    Thousand_SW DECIMAL,
    "Oil%" DECIMAL,
    Oil_yield DECIMAL,
    N DECIMAL,
    P DECIMAL,
    K DECIMAL,
    Na DECIMAL,
    Ca DECIMAL,
    Mg DECIMAL,
    Fe DECIMAL,
    Mn DECIMAL,
    Zn DECIMAL,
    Cu DECIMAL,
    "Chl a" DECIMAL,
    "Chl b" DECIMAL,
    RWC DECIMAL,
    "Ionic L" DECIMAL,
    Prolin DECIMAL,
    "K/Na" DECIMAL
)
""")

with open("AgriTrial+Data+Canola.csv", "r", newline="", encoding="utf-8-sig") as file:
    reader = csv.reader(file)

    # Skip the first row
    next(reader, None)

    # 4. Insert each row into the database
    for row in reader:
        if not row:
            continue

        cur.execute("""
            INSERT INTO trial_site VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
            )
        """, row)


conn.commit()

conn.close()
