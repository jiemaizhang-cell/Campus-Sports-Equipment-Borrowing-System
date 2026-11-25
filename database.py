"""SQLite storage for registered test cards and equipment availability."""

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path


def is_registered_card(database_path, card_id):
    """Look up a format-validated card ID in the local database."""
    with _open_database(database_path) as database:
        return database.execute(
            "SELECT 1 FROM registered_cards WHERE card_id = ?", (card_id,)
        ).fetchone() is not None


def list_equipment(database_path):
    """Read the current available quantity for each item."""
    with _open_database(database_path) as database:
        database.row_factory = sqlite3.Row
        return database.execute(
            "SELECT name, available_quantity FROM equipment ORDER BY item_id"
        ).fetchall()


@contextmanager
def _open_database(database_path):
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as database:
        _initialize_database(database)
        yield database


def _table_names(database):
    return {name for (name,) in database.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _initialize_database(database):
    if {"registered_cards", "equipment"}.issubset(_table_names(database)):
        return

    # Create and seed missing tables together. Keep data from existing prototype databases.
    with database:
        database.execute("BEGIN IMMEDIATE")
        tables = _table_names(database)
        if "registered_cards" not in tables:
            database.execute(
                "CREATE TABLE registered_cards (card_id TEXT NOT NULL PRIMARY KEY)"
            )
            database.execute(
                "INSERT INTO registered_cards (card_id) VALUES (?)", ("20260001",)
            )
        if "equipment" not in tables:
            database.execute("""
                CREATE TABLE equipment (
                    item_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    available_quantity INTEGER NOT NULL CHECK (
                        typeof(available_quantity) = 'integer' AND available_quantity >= 0
                    )
                )
            """)
            database.executemany(
                "INSERT INTO equipment (item_id, name, available_quantity) VALUES (?, ?, ?)",
                [(1, "Basketball", 5), (2, "Football", 3), (3, "Badminton racket", 0)],
            )
