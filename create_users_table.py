from database import get_db_connection

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    password TEXT NOT NULL
);
"""


def main() -> None:
    conn = get_db_connection()
    try:
        conn.execute(CREATE_USERS_TABLE)
        conn.commit()
        print("Table users created successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
