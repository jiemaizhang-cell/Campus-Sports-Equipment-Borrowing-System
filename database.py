"""SQLite storage for the prototype's registered test cards."""

import sqlite3
from contextlib import closing
from pathlib import Path


def is_registered_card(database_path, card_id):
    """Look up a format-validated card ID in the local database."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as database:
        _initialize_registered_cards(database)
        return database.execute(
            "SELECT 1 FROM registered_cards WHERE card_id = ?", (card_id,)
        ).fetchone() is not None


def _initialize_registered_cards(database):
    table_query = """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = 'registered_cards'
    """
    if database.execute(table_query).fetchone() is not None:
        return

    # Serialize first-time setup in case multiple requests arrive together.
    with database:
        database.execute("BEGIN IMMEDIATE")
        if database.execute(table_query).fetchone() is None:
            database.execute(
                "CREATE TABLE registered_cards (card_id TEXT NOT NULL PRIMARY KEY)"
            )
            database.execute(
                "INSERT INTO registered_cards (card_id) VALUES (?)", ("20260001",)
            )
