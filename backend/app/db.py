"""Tiny JSON document store on SQLite. Fine for ~1k rows; swap for real tables later if needed."""
import json
import sqlite3
import threading

from . import config

DOC_TABLES = ["blocks", "households", "cases", "teams", "shelters", "claims", "contractors", "meta"]
LOG_TABLES = ["messages", "trace", "audit"]

_lock = threading.RLock()
_conn = None


def conn():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        for t in DOC_TABLES:
            _conn.execute(f"CREATE TABLE IF NOT EXISTS {t}(id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        for t in LOG_TABLES:
            _conn.execute(f"CREATE TABLE IF NOT EXISTS {t}(id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL)")
        _conn.commit()
    return _conn


def put(table, id, obj):
    with _lock:
        conn().execute(f"INSERT OR REPLACE INTO {table}(id, data) VALUES (?, ?)", (str(id), json.dumps(obj)))
        conn().commit()


def put_many(table, objs):
    with _lock:
        conn().executemany(
            f"INSERT OR REPLACE INTO {table}(id, data) VALUES (?, ?)",
            [(str(o["id"]), json.dumps(o)) for o in objs],
        )
        conn().commit()


def get(table, id):
    with _lock:
        row = conn().execute(f"SELECT data FROM {table} WHERE id = ?", (str(id),)).fetchone()
    return json.loads(row[0]) if row else None


def all_docs(table):
    with _lock:
        rows = conn().execute(f"SELECT id, data FROM {table} ORDER BY id").fetchall()
    out = []
    for rid, data in rows:
        d = json.loads(data)
        d.setdefault("id", rid)
        out.append(d)
    return out


def append(table, obj):
    with _lock:
        cur = conn().execute(f"INSERT INTO {table}(data) VALUES (?)", (json.dumps(obj),))
        conn().commit()
        return cur.lastrowid


def recent(table, limit=30):
    with _lock:
        rows = conn().execute(f"SELECT id, data FROM {table} ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{**json.loads(d), "id": i} for i, d in rows]


def reset():
    with _lock:
        for t in DOC_TABLES + LOG_TABLES:
            conn().execute(f"DELETE FROM {t}")
        try:
            conn().execute("DELETE FROM sqlite_sequence")  # restart log ids at 1
        except sqlite3.OperationalError:
            pass
        conn().commit()
