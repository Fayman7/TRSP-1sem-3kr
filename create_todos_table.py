from database import get_db_connection

CREATE_TODOS_TABLE = """
CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0
);
"""


def main() -> None:
    conn = get_db_connection()
    try:
        conn.execute(CREATE_TODOS_TABLE)
        conn.commit()
        print("Table todos created successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
