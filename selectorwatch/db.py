import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_default_path = Path(__file__).parent.parent / "data" / "selectorwatch.db"
DB_PATH = Path(os.environ.get("DB_PATH", _default_path))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sites (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    name                   TEXT    NOT NULL,
    url                    TEXT    NOT NULL UNIQUE,
    check_interval_minutes INTEGER NOT NULL DEFAULT 60,
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS selectors (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id       INTEGER NOT NULL REFERENCES sites(id),
    name          TEXT    NOT NULL,
    selector      TEXT    NOT NULL,
    selector_type TEXT    NOT NULL CHECK(selector_type IN ('css', 'xpath')),
    expected_type TEXT    NOT NULL DEFAULT 'any'
                          CHECK(expected_type IN ('text', 'number', 'url', 'any')),
    min_results   INTEGER NOT NULL DEFAULT 1,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    selector_id     INTEGER NOT NULL REFERENCES selectors(id),
    html_fragment   TEXT,
    extracted_value TEXT,
    status          TEXT NOT NULL CHECK(status IN ('ok', 'failed')),
    checked_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS change_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    selector_id         INTEGER NOT NULL REFERENCES selectors(id),
    detected_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    change_type         TEXT,
    old_html_fragment   TEXT,
    new_html_fragment   TEXT,
    diff_report         TEXT,
    suggested_selectors TEXT,
    validation_results  TEXT,
    resolved            INTEGER NOT NULL DEFAULT 0,
    resolved_at         TIMESTAMP
);
"""


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(_SCHEMA)
