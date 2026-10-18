
import os

import requests

TIMEOUT = 15


class SupabaseNotConfigured(Exception):
    pass


class SupabaseClient:
    def __init__(self, url=None, key=None):
        self.url = (url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.key = key or os.getenv("SUPABASE_KEY", "")

    @property
    def configured(self):
        return bool(self.url and self.key)

    def _headers(self):
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            # upsert on primary key, don't echo rows back
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }

    def upsert(self, table, rows):

        if not self.configured:
            raise SupabaseNotConfigured("SUPABASE_URL / SUPABASE_KEY not set")
        if not rows:
            return 0
        resp = requests.post(
            f"{self.url}/rest/v1/{table}?on_conflict=id",
            json=rows, headers=self._headers(), timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return len(rows)

    def sync(self, farmers, trials):

        return {
            "farmers": self.upsert("farmers", farmers),
            "trials": self.upsert("trials", trials),
        }
