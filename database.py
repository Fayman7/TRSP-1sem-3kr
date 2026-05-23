import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).parent / "app.db"


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn
