# AgroTrial MVP

Flask prototype: login, farmer/yield capture, trial-measurement capture, JSON API, dashboard, group confidence-interval charts, Supabase sync.

| Component | Tech | Files |
|---|---|---|
| App + API | Flask | `app.py` |
| Logins | SQLite `login.sqlite`, hashed PINs | `auth.py` |
| Farmer / yield data | Python list or SQLite (`farm.db`) | `storage.py` |
| Trial measurements | SQLite `agritrial.db`, table `trial_data` | `trial_db.py` |
| Dashboard + CI charts | Pandas + Matplotlib (+ SciPy) | `dashboard.py`, `ci.py` |
| Online DB | Supabase REST | `supabase_client.py`, `schema.sql` |
| Forms and pages | HTML + CSS | `templates/`, `static/style.css` |

## Run it

```bash
pip install -r requirements.txt
python seed.py            # optional: demo data + demo logins
python app.py             # http://127.0.0.1:5000
python test_app.py        # runs the test suite
```

Demo logins (created when `login.sqlite` is empty): `USERONE` / `0000` and `USERTWO` / `0001`.
**Turn them off before real use:** `DEMO_USERS=0 python app.py`, then create real accounts.

## Login database

Your original script is now `auth.py`:

- Table `details` in `login.sqlite`. PINs are stored as salted hashes, not plain text.
- `pin` is no longer UNIQUE (two people can choose the same PIN, and a UNIQUE column reveals which PINs are taken).
- Usernames are case-insensitive. PIN is 4 to 8 digits.
- 5 wrong attempts lock a username for 5 minutes (a 4-digit PIN is otherwise easy to brute-force).
- An old `login.sqlite` with plain-text PINs is converted automatically on first start.
- Every page except login, register and `/api/health` needs a login.
- Set `SECRET_KEY` in production (otherwise a random one is made on each start and everyone is logged out), and `ALLOW_REGISTRATION=0` to close open sign-up.

## Trial measurements

`trial_db.py` is your database script: table `trial_data` in `agritrial.db`, same required fields (site, date, crop, treatment group, observer) and the same 14 optional measurements. Run `python trial_db.py` to create it with your 5 sample rows. Enter data at `/trial-data`.

## CI chart

`/ci` has two parts:

1. **From the trial database:** pick a measurement, compare by treatment group, crop or site, optionally filter to one crop. Filtering by crop matters when crops have different scales.
2. **From a CSV:** your "real CI chart" script as a web form. Upload a CSV, name the value column, the group column and the groups (for example `Mg`, `Block`, `Control, Combined`).

Command line version of your script:

```bash
python ci.py "AgriTrial+Data+Canola.csv" Mg Block Control Combined
```

The interval is mean ± t(0.975, n−1) × SD/√n. A group needs at least 2 values.

## API (Postman, curl, browser)

The API uses the same login. In Postman, `POST /api/login` first; Postman keeps the session cookie for later requests.

| Method | Path | Notes |
|---|---|---|
| POST | `/api/login` | `{"username": "USERONE", "pin": "0000"}` |
| POST | `/api/logout` | |
| GET | `/api/health` | public |
| GET / POST | `/api/trials` | farmer + yield records (201, or 422 with field errors) |
| GET / POST | `/api/trial-data` | measurement rows from `trial_data` |
| GET | `/api/ci?column=yield_value&group_by=treatment_group&crop=Lettuce&groups=Control,Treatment 1` | CI stats per group |
| GET | `/api/farmers`, `/api/summary` | |
| POST | `/api/sync` | push farm data to Supabase (503 if not configured) |

```bash
curl -c jar -X POST http://127.0.0.1:5000/api/login -H "Content-Type: application/json" \
     -d '{"username":"USERONE","pin":"0000"}'
curl -b jar -X POST http://127.0.0.1:5000/api/trial-data -H "Content-Type: application/json" \
     -d '{"site":"Site A","trial_date":"2026-10-01","crop":"Lettuce","treatment_group":"Control","observer":"Observer 1","yield_value":210}'
```

## Storage options

```bash
STORAGE_BACKEND=list python app.py    # farm data in memory only
STORAGE_BACKEND=sqlite python app.py  # default (farm.db)
SQLITE_PATH=... LOGIN_DB=... TRIAL_DB=... python app.py   # move the database files
```

## Supabase

1. Run `schema.sql` in the Supabase SQL editor.
2. `export SUPABASE_URL=...` and `export SUPABASE_KEY=...` (use the service-role key on the server only).
3. Click **Sync to Supabase** on the dashboard or `POST /api/sync`.

Sync currently covers the farmer and yield records. `trial_data` and logins stay local; adding a `trial_data` table to Supabase is the natural next step. Supabase Auth could later replace `login.sqlite`.
