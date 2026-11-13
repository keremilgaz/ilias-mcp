"""Short-lived local approval records shared by MCP processes."""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import time
from contextlib import closing, contextmanager
from pathlib import Path


class CardStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def _open(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.execute("PRAGMA secure_delete=ON")
            db.execute(
                "CREATE TABLE IF NOT EXISTS pending_cards ("
                "ref TEXT PRIMARY KEY, token TEXT NOT NULL UNIQUE, expires REAL NOT NULL, payload TEXT NOT NULL)"
            )
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM pending_cards WHERE expires <= ?", (time.time(),))
            yield db

    def create(self, payload: dict) -> str | None:
        with self._open() as db:
            if db.execute("SELECT count(*) FROM pending_cards").fetchone()[0] >= 32:
                return None
            ref = secrets.token_hex(16)
            db.execute("INSERT INTO pending_cards VALUES (?, ?, ?, ?)",
                       (ref, secrets.token_urlsafe(32), time.time() + 300, json.dumps(payload)))
            return ref

    def preview(self, ref: str) -> dict | None:
        if not self.path.is_file():
            return None
        with self._open() as db:
            row = db.execute("SELECT token, payload FROM pending_cards WHERE ref = ?", (ref,)).fetchone()
            if row is None:
                return None
            return {"token": row[0], "preview": json.loads(row[1])["preview"]}

    def take(self, token: str) -> dict | None:
        if not self.path.is_file():
            return None
        with self._open() as db:
            row = db.execute("SELECT payload FROM pending_cards WHERE token = ?", (token,)).fetchone()
            if row is None:
                return None
            db.execute("DELETE FROM pending_cards WHERE token = ?", (token,))
            return json.loads(row[0])
