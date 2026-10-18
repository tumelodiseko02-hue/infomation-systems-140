
import os
import re
import sqlite3
import time
from contextlib import closing

from werkzeug.security import check_password_hash, generate_password_hash

USER_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
PIN_RE = re.compile(r"^\d{4,8}$")
MAX_FAILS = 5
LOCK_SECONDS = 300
DEMO_USERS = (("USERONE", "0000"), ("USERTWO", "0001"))
_DUMMY_HASH = generate_password_hash("00000000")  # equalises timing for unknown users


class AuthDB:
    def __init__(self, path=None, seed_demo=None):
        self.path = path or os.getenv("LOGIN_DB", "login.sqlite")
        self._fails = {}  # username.lower() -> (count, first_fail_time)
        self._create_and_migrate()
        if seed_demo is None:
            seed_demo = os.getenv("DEMO_USERS", "1") == "1"
        if seed_demo and self.count() == 0:
            for name, pin in DEMO_USERS:
                self.create_user(name, pin)

    def _conn(self):
        return sqlite3.connect(self.path)

    def _create_and_migrate(self):
        with closing(self._conn()) as c, c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS details ("
                "id INTEGER PRIMARY KEY, "
                "username TEXT NOT NULL UNIQUE COLLATE NOCASE, "
                "pin_hash TEXT NOT NULL)"
            )
            cols = {r[1] for r in c.execute("PRAGMA table_info(details)")}
            if "pin" in cols and "pin_hash" not in cols:  # old plain-text table
                c.execute("ALTER TABLE details ADD COLUMN pin_hash TEXT")
                for row_id, pin in c.execute("SELECT id, pin FROM details").fetchall():
                    c.execute("UPDATE details SET pin_hash = ?, pin = NULL WHERE id = ?",
                              (generate_password_hash(str(pin)), row_id))

    def count(self):
        with closing(self._conn()) as c:
            return c.execute("SELECT COUNT(*) FROM details").fetchone()[0]

    def create_user(self, username, pin):
        """Create an account. Raises ValueError with a user-facing message."""
        username, pin = (username or "").strip(), (pin or "").strip()
        if not USER_RE.match(username):
            raise ValueError("Username must be 3-30 characters: letters, numbers, . _ -")
        if not PIN_RE.match(pin):
            raise ValueError("PIN must be 4 to 8 digits")
        try:
            with closing(self._conn()) as c, c:
                c.execute("INSERT INTO details (username, pin_hash) VALUES (?, ?)",
                          (username, generate_password_hash(pin)))
        except sqlite3.IntegrityError:
            raise ValueError("That username is already taken") from None

    def _locked(self, key):
        count, first = self._fails.get(key, (0, 0))
        if count >= MAX_FAILS and time.time() - first < LOCK_SECONDS:
            return True
        if count and time.time() - first >= LOCK_SECONDS:
            self._fails.pop(key, None)
        return False

    def verify(self, username, pin):
        """Return (status, canonical_username); status is 'ok', 'bad' or 'locked'."""
        username, pin = (username or "").strip(), (pin or "").strip()
        key = username.lower()
        if self._locked(key):
            return "locked", None
        with closing(self._conn()) as c:
            row = c.execute(
                "SELECT username, pin_hash FROM details WHERE username = ? COLLATE NOCASE",
                (username,),
            ).fetchone()
        ok = check_password_hash(row[1] if row else _DUMMY_HASH, pin) and row is not None
        if ok:
            self._fails.pop(key, None)
            return "ok", row[0]
        count, first = self._fails.get(key, (0, time.time()))
        self._fails[key] = (count + 1, first)
        return "bad", None
