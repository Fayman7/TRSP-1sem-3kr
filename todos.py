import sqlite3

from fastapi import APIRouter, HTTPException, status

from database import get_db_connection
from models import Todo, TodoCreate, TodoUpdate

router = APIRouter()


def _row_to_todo(row: sqlite3.Row) -> Todo:
    return Todo(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        completed=bool(row["completed"]),
    )


def _get_todo_row(conn: sqlite3.Connection, todo_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()


@router.post("/todos", status_code=status.HTTP_201_CREATED, response_model=Todo)
def create_todo(todo: TodoCreate):
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO todos (title, description, completed) VALUES (?, ?, 0)",
            (todo.title, todo.description),
        )
        conn.commit()
        row = _get_todo_row(conn, cursor.lastrowid)
        return _row_to_todo(row)
    finally:
        conn.close()


@router.get("/todos/{todo_id}", response_model=Todo)
def get_todo(todo_id: int):
    conn = get_db_connection()
    try:
        row = _get_todo_row(conn, todo_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Todo not found",
            )
        return _row_to_todo(row)
    finally:
        conn.close()


@router.put("/todos/{todo_id}", response_model=Todo)
def update_todo(todo_id: int, todo: TodoUpdate):
    conn = get_db_connection()
    try:
        row = _get_todo_row(conn, todo_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Todo not found",
            )

        conn.execute(
            "UPDATE todos SET title = ?, description = ?, completed = ? WHERE id = ?",
            (todo.title, todo.description, int(todo.completed), todo_id),
        )
        conn.commit()
        updated_row = _get_todo_row(conn, todo_id)
        return _row_to_todo(updated_row)
    finally:
        conn.close()


@router.delete("/todos/{todo_id}")
def delete_todo(todo_id: int):
    conn = get_db_connection()
    try:
        row = _get_todo_row(conn, todo_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Todo not found",
            )

        conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        conn.commit()
        return {"message": "Todo deleted successfully"}
    finally:
        conn.close()
