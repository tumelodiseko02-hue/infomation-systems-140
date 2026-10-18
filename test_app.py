
import io
import os
import sqlite3
import tempfile

from app import create_app
from auth import AuthDB
from storage import ListStorage, SQLiteStorage
from trial_db import TrialDB

GOOD = {"name": "Amina Juma", "phone": "0712345678", "village": "Mbeya",
        "farm_size_ha": 2.5, "crop": "Maize", "treatment": "Fertilizer",
        "planting_date": "2026-02-15", "yield_kg_per_ha": 3650}

TRIAL = {"site": "Site A", "trial_date": "2026-10-01", "crop": "Lettuce",
         "treatment_group": "Control", "observer": "Observer 1",
         "yield_value": 210.0, "leaf_count": 9}


class FakeSupabase:
    configured = True

    def sync(self, farmers, trials):
        return {"farmers": len(farmers), "trials": len(trials)}


def fresh(kind, tmp, login=True):
    """Build an app on throw-away databases; optionally log in as USERONE."""
    storage = ListStorage() if kind == "list" else SQLiteStorage(os.path.join(tmp, "farm.db"))
    app = create_app(storage=storage, supabase=FakeSupabase(),
                     auth=AuthDB(os.path.join(tmp, "login.sqlite"), seed_demo=True),
                     trials=TrialDB(os.path.join(tmp, "agritrial.db")))
    client = app.test_client()
    if login:
        assert client.post("/api/login", json={"username": "USERONE", "pin": "0000"}).status_code == 200
    return client


#  authentication
def test_requires_login(kind, tmp):
    c = fresh(kind, tmp, login=False)
    r = c.get("/dashboard")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert c.get("/api/trials").status_code == 401
    assert c.get("/chart.png").status_code == 302
    assert c.get("/api/health").status_code == 200
    assert c.get("/login").status_code == 200


def test_login_logout(kind, tmp):
    c = fresh(kind, tmp, login=False)
    assert c.post("/login", data={"username": "USERONE", "pin": "9999"}).status_code == 401
    assert c.post("/api/login", json={"username": "nobody", "pin": "0000"}).status_code == 401
    r = c.post("/login", data={"username": "userone", "pin": "0000"})  # case-insensitive
    assert r.status_code == 302 and c.get("/dashboard").status_code == 200
    c.post("/logout")
    assert c.get("/dashboard").status_code == 302


def test_open_redirect_blocked(kind, tmp):
    c = fresh(kind, tmp, login=False)
    r = c.post("/login", data={"username": "USERONE", "pin": "0000", "next": "//evil.example"})
    assert r.headers["Location"] == "/"
    r = c.post("/login", data={"username": "USERONE", "pin": "0000", "next": "http://evil.example"})
    assert r.headers["Location"] == "/"


def test_lockout(kind, tmp):
    c = fresh(kind, tmp, login=False)
    for _ in range(5):
        assert c.post("/api/login", json={"username": "USERTWO", "pin": "1111"}).status_code == 401
    assert c.post("/api/login", json={"username": "USERTWO", "pin": "0001"}).status_code == 429


def test_register_and_hashing(kind, tmp):
    c = fresh(kind, tmp, login=False)
    assert c.post("/register", data={"username": "ab", "pin": "1234", "pin2": "1234"}).status_code == 400
    assert c.post("/register", data={"username": "newuser", "pin": "12", "pin2": "12"}).status_code == 400
    assert c.post("/register", data={"username": "newuser", "pin": "1234", "pin2": "9999"}).status_code == 400
    assert c.post("/register", data={"username": "userone", "pin": "1234", "pin2": "1234"}).status_code == 400
    assert c.post("/register", data={"username": "newuser", "pin": "4321", "pin2": "4321"}).status_code == 201
    assert c.post("/api/login", json={"username": "NewUser", "pin": "4321"}).status_code == 200
    with sqlite3.connect(os.path.join(tmp, "login.sqlite")) as db:
        (stored,) = db.execute("SELECT pin_hash FROM details WHERE username='newuser'").fetchone()
    assert stored.startswith(("scrypt:", "pbkdf2:")) and "4321" not in stored


def test_migrates_plaintext_pins(kind, tmp):
    path = os.path.join(tmp, "old.sqlite")
    with sqlite3.connect(path) as db:  # your original schema, plain-text pins
        db.execute("CREATE TABLE details(id INTEGER PRIMARY KEY, username TEXT UNIQUE, pin TEXT UNIQUE)")
        db.execute("INSERT INTO details(username,pin) VALUES('USERONE','0000')")
    auth = AuthDB(path, seed_demo=False)
    assert auth.verify("USERONE", "0000") == ("ok", "USERONE")
    assert auth.verify("USERONE", "1234")[0] == "bad"
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT pin FROM details").fetchone()[0] is None


# farmer / yield data
def test_pages_load(kind, tmp):
    c = fresh(kind, tmp)
    for path in ("/", "/dashboard", "/trial-data", "/ci"):
        assert c.get(path).status_code == 200, path
    assert c.get("/api/health").get_json()["status"] == "ok"


def test_api_post_and_get(kind, tmp):
    c = fresh(kind, tmp)
    assert c.post("/api/trials", json=GOOD).status_code == 201
    c.post("/api/trials", json={**GOOD, "yield_kg_per_ha": 3400})
    assert len(c.get("/api/farmers").get_json()) == 1
    assert len(c.get("/api/trials").get_json()) == 2
    assert len(c.get("/api/trials?crop=maize").get_json()) == 2
    assert c.get("/api/trials?crop=beans").get_json() == []


def test_validation(kind, tmp):
    c = fresh(kind, tmp)
    r = c.post("/api/trials", json={"name": "", "yield_kg_per_ha": "abc"})
    assert r.status_code == 422
    assert {"name", "phone", "crop", "yield_kg_per_ha"} <= set(r.get_json()["fields"])
    assert c.post("/api/trials", data="nope", content_type="text/plain").status_code == 400
    assert c.post("/api/trials", json={**GOOD, "yield_kg_per_ha": "nan"}).status_code == 422


def test_form_submit(kind, tmp):
    c = fresh(kind, tmp)
    assert c.post("/submit", data=GOOD).status_code == 302
    bad = c.post("/submit", data={"name": "x"})
    assert bad.status_code == 400 and b"Required" in bad.data


def test_summary_and_chart(kind, tmp):
    c = fresh(kind, tmp)
    assert c.get("/chart.png").data[:4] == b"\x89PNG"  # empty case
    for y in (3000, 3200, 3400, 3100):
        c.post("/api/trials", json={**GOOD, "yield_kg_per_ha": y})
    c.post("/api/trials", json={**GOOD, "crop": "Beans", "yield_kg_per_ha": 1200})
    s = c.get("/api/summary").get_json()
    maize = next(x for x in s["by_crop"] if x["crop"] == "Maize")
    assert maize["n"] == 4 and maize["lower"] < maize["mean"] < maize["upper"]
    assert next(x for x in s["by_crop"] if x["crop"] == "Beans")["lower"] is None
    assert c.get("/chart.png").data[:4] == b"\x89PNG"


def test_sync(kind, tmp):
    c = fresh(kind, tmp)
    c.post("/api/trials", json=GOOD)
    assert c.post("/api/sync").get_json()["synced"] == {"farmers": 1, "trials": 1}


def test_sync_not_configured(kind, tmp):
    from supabase_client import SupabaseClient
    app = create_app(storage=ListStorage(), supabase=SupabaseClient(url="", key=""),
                     auth=AuthDB(os.path.join(tmp, "l.sqlite"), seed_demo=True),
                     trials=TrialDB(os.path.join(tmp, "t.db")))
    c = app.test_client()
    c.post("/api/login", json={"username": "USERONE", "pin": "0000"})
    assert c.post("/api/sync").status_code == 503


# trial measurements + CI chart
def test_trial_data_api(kind, tmp):
    c = fresh(kind, tmp)
    r = c.post("/api/trial-data", json=TRIAL)
    assert r.status_code == 201 and r.get_json()["id"] == 1
    assert c.get("/api/trial-data").get_json()[0]["yield_value"] == 210.0
    bad = c.post("/api/trial-data", json={"site": "", "trial_date": "01/10/2026", "leaf_count": 2.5,
                                          "ph": "inf", "yield_value": "abc"})
    assert bad.status_code == 422
    assert {"site", "trial_date", "crop", "treatment_group", "observer",
            "leaf_count", "ph", "yield_value"} <= set(bad.get_json()["fields"])


def test_trial_data_form(kind, tmp):
    c = fresh(kind, tmp)
    form = {k: v for k, v in TRIAL.items()}
    assert c.post("/trial-data", data=form).status_code == 302
    assert len(c.get("/api/trial-data").get_json()) == 1
    assert c.post("/trial-data", data={"site": "x"}).status_code == 400


def _load_ci_rows(c):
    for group, vals in (("Control", (10, 11, 12, 13)), ("Treatment 1", (14, 15, 16, 18))):
        for v in vals:
            c.post("/api/trial-data", json={**TRIAL, "treatment_group": group, "yield_value": v})
    c.post("/api/trial-data", json={**TRIAL, "treatment_group": "Lonely", "yield_value": 5})


def test_ci_api_and_page(kind, tmp):
    c = fresh(kind, tmp)
    assert c.get("/api/ci?column=yield_value").status_code == 422  # no data yet
    _load_ci_rows(c)
    r = c.get("/api/ci?column=yield_value&group_by=treatment_group")
    assert r.status_code == 200
    groups = {g["group"]: g for g in r.get_json()["groups"]}
    assert groups["Control"]["n"] == 4 and abs(groups["Control"]["mean"] - 11.5) < 1e-9
    assert groups["Control"]["lower"] < 11.5 < groups["Control"]["upper"]
    assert groups["Lonely"]["lower"] is None  # one value: no CI
    only = c.get("/api/ci?column=yield_value&groups=Control,Treatment+1").get_json()["groups"]
    assert [g["group"] for g in only] == ["Control", "Treatment 1"]
    c.post("/api/trial-data", json={**TRIAL, "crop": "Tomato", "treatment_group": "Control", "yield_value": 900})
    c.post("/api/trial-data", json={**TRIAL, "crop": "Tomato", "treatment_group": "Control", "yield_value": 910})
    lettuce = c.get("/api/ci?column=yield_value&crop=lettuce&groups=Control").get_json()
    assert lettuce["groups"][0]["n"] == 4 and lettuce["crop"] == "lettuce"
    assert c.get("/api/ci?column=yield_value&crop=Nothing").status_code == 422
    page = c.get("/ci?column=yield_value&group_by=treatment_group")
    assert page.status_code == 200 and b"data:image/png;base64," in page.data


def test_ci_rejects_bad_params(kind, tmp):
    c = fresh(kind, tmp)
    c.post("/api/trial-data", json=TRIAL)
    for q in ("column=yield_value;DROP TABLE trial_data", "column=id", "column=yield_value&group_by=observer"):
        assert c.get(f"/api/ci?{q}").status_code == 422, q
    assert len(c.get("/api/trial-data").get_json()) == 1  # table intact


def test_ci_csv_upload(kind, tmp):
    c = fresh(kind, tmp)
    csv = b"Block,Mg\nControl,1.0\nControl,1.2\nControl,1.1\nCombined,1.6\nCombined,1.8\nCombined,1.7\n"

    def post(**over):
        data = {"file": (io.BytesIO(csv), "canola.csv"), "column": "Mg",
                "group_column": "Block", "groups": "Control, Combined", **over}
        return c.post("/ci/csv", data=data, content_type="multipart/form-data")

    ok = post()
    assert ok.status_code == 200 and b"data:image/png;base64," in ok.data and b"Combined" in ok.data
    assert post(column="Nope").status_code == 422
    assert c.post("/ci/csv", data={"column": "Mg", "group_column": "Block"}).status_code == 422
    junk = c.post("/ci/csv", data={"file": (io.BytesIO(b"\xff\xfe\x00bad"), "x.csv"),
                                   "column": "Mg", "group_column": "Block"},
                  content_type="multipart/form-data")
    assert junk.status_code == 422


TESTS = [test_requires_login, test_login_logout, test_open_redirect_blocked, test_lockout,
         test_register_and_hashing, test_migrates_plaintext_pins, test_pages_load,
         test_api_post_and_get, test_validation, test_form_submit, test_summary_and_chart,
         test_sync, test_sync_not_configured, test_trial_data_api, test_trial_data_form,
         test_ci_api_and_page, test_ci_rejects_bad_params, test_ci_csv_upload]

if __name__ == "__main__":
    for kind in ("list", "sqlite"):
        for t in TESTS:
            with tempfile.TemporaryDirectory() as d:
                t(kind, d)
            print(f"ok  [{kind}] {t.__name__}")
    print("ALL PASSED")
