
import os
import sqlite3
import uuid
from datetime import datetime, timezone

FARMER_FIELDS = ["id", "name", "phone", "village", "farm_size_ha", "created_at"]
TRIAL_FIELDS = [
    "id", "farmer_id", "crop", "variety", "treatment",
    "planting_date", "yield_kg_per_ha", "notes", "created_at",
]


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id():
    return str(uuid.uuid4())


class ListStorage:


    name = "list"

    def __init__(self):
        self._farmers = []
        self._trials = []

    def find_farmer_by_phone(self, phone):
        return next((f for f in self._farmers if f["phone"] == phone), None)

    def add_farmer(self, data):
        farmer = {
            "id": _new_id(),
            "name": data["name"],
            "phone": data["phone"],
            "village": data.get("village"),
            "farm_size_ha": data.get("farm_size_ha"),
            "created_at": _now(),
        }
        self._farmers.append(farmer)
        return farmer

    def add_trial(self, data):
        trial = {
            "id": _new_id(),
            "farmer_id": data["farmer_id"],
            "crop": data["crop"],
            "variety": data.get("variety"),
            "treatment": data.get("treatment"),
            "planting_date": data.get("planting_date"),
            "yield_kg_per_ha": data["yield_kg_per_ha"],
            "notes": data.get("notes"),
            "created_at": _now(),
        }
        self._trials.append(trial)
        return trial

    def list_farmers(self):
        return list(self._farmers)

    def list_trials(self):
        return list(self._trials)


class SQLiteStorage:

    name = "sqlite"

    def __init__(self, path="farm.db"):
        self.path = path
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS farmers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL UNIQUE,
                    village TEXT,
                    farm_size_ha REAL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trials (
                    id TEXT PRIMARY KEY,
                    farmer_id TEXT NOT NULL REFERENCES farmers(id),
                    crop TEXT NOT NULL,
                    variety TEXT,
                    treatment TEXT,
                    planting_date TEXT,
                    yield_kg_per_ha REAL NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _rows(self, sql, args=()):
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(sql, args).fetchall()]
        finally:
            conn.close()

    def find_farmer_by_phone(self, phone):
        rows = self._rows("SELECT * FROM farmers WHERE phone = ?", (phone,))
        return rows[0] if rows else None

    def add_farmer(self, data):
        farmer = {
            "id": _new_id(),
            "name": data["name"],
            "phone": data["phone"],
            "village": data.get("village"),
            "farm_size_ha": data.get("farm_size_ha"),
            "created_at": _now(),
        }
        with self._conn() as c:
            c.execute(
                "INSERT INTO farmers VALUES (:id,:name,:phone,:village,:farm_size_ha,:created_at)",
                farmer,
            )
        return farmer

    def add_trial(self, data):
        trial = {
            "id": _new_id(),
            "farmer_id": data["farmer_id"],
            "crop": data["crop"],
            "variety": data.get("variety"),
            "treatment": data.get("treatment"),
            "planting_date": data.get("planting_date"),
            "yield_kg_per_ha": data["yield_kg_per_ha"],
            "notes": data.get("notes"),
            "created_at": _now(),
        }
        with self._conn() as c:
            c.execute(
                "INSERT INTO trials VALUES (:id,:farmer_id,:crop,:variety,:treatment,"
                ":planting_date,:yield_kg_per_ha,:notes,:created_at)",
                trial,
            )
        return trial

    def list_farmers(self):
        return self._rows("SELECT * FROM farmers ORDER BY created_at")

    def list_trials(self):
        return self._rows("SELECT * FROM trials ORDER BY created_at")


def make_storage(backend=None, path=None):
    backend = (backend or os.getenv("STORAGE_BACKEND", "sqlite")).lower()
    if backend == "list":
        return ListStorage()
    return SQLiteStorage(path or os.getenv("SQLITE_PATH", "farm.db"))
