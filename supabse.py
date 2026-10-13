import sqlite3
from supabase import create_client

url = "https://zumphozcyiiefdauawzw.supabase.co"
key = "sb_publishable_KE-imwFlwyZHAflwQb937Q_c4W1mI3J"

supabase = create_client(url, key)

conn = sqlite3.connect("canola.sqlite")
conn.row_factory = sqlite3.Row

cur = conn.cursor()

cur.execute("SELECT * FROM trial_site")
rows = cur.fetchall()

for row in rows:
    data = {}

    for column in row.keys():
        data[column] = row[column]

        if isinstance(data[column], str):
            data[column] = data[column].strip().replace(". ", ".")

    supabase.table("trial_site").insert(data).execute()

    print("Record uploaded")

conn.close()

print("All records uploaded!")