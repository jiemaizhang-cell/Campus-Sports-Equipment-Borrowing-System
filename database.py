"""SQLite storage for test cards, equipment availability, and loans."""

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path


class ActiveLoanExists(Exception):
    """The card already has an outstanding loan."""


def record_loan(database, card_id, item_id):
    """Insert an active loan in the caller's transaction and return its ID."""
    loan = database.execute("""
        INSERT INTO loans (card_id, item_id)
        VALUES (?, ?)
        ON CONFLICT (card_id) WHERE returned_at IS NULL DO NOTHING
    """, (card_id, item_id))
    if loan.rowcount == 0:
        raise ActiveLoanExists("Return the current equipment before borrowing another item.")
    return loan.lastrowid


def find_card_loan_status(database_path, card_id):
    """Find a registered card and any outstanding loan for it."""
    with _open_database(database_path) as database:
        database.row_factory = sqlite3.Row
        return database.execute("""
            SELECT cards.card_id, equipment.name AS item_name
            FROM registered_cards AS cards
            LEFT JOIN loans ON loans.card_id = cards.card_id AND loans.returned_at IS NULL
            LEFT JOIN equipment ON equipment.item_id = loans.item_id
            WHERE cards.card_id = ?
            ORDER BY loans.loan_id DESC
            LIMIT 1
        """, (card_id,)).fetchone()


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
        database.execute("PRAGMA foreign_keys = ON")
        _initialize_database(database)
        yield database


def _schema_names(database):
    return {
        name for (name,) in database.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')"
        )
    }


def _initialize_database(database):
    required = {"registered_cards", "equipment", "loans", "unique_active_loan_per_card"}
    if required.issubset(_schema_names(database)):
        return

    # Apply schema changes and demo seeds together while preserving existing rows.
    with database:
        database.execute("BEGIN IMMEDIATE")
        schema = _schema_names(database)
        if "registered_cards" not in schema:
            database.execute(
                "CREATE TABLE registered_cards (card_id TEXT NOT NULL PRIMARY KEY)"
            )
            database.execute(
                "INSERT INTO registered_cards (card_id) VALUES (?)", ("20260001",)
            )
        if "equipment" not in schema:
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
        new_loans_table = "loans" not in schema
        if new_loans_table:
            _create_loans_table(database)
        if "unique_active_loan_per_card" not in schema:
            database.execute("""
                CREATE UNIQUE INDEX unique_active_loan_per_card
                ON loans (card_id) WHERE returned_at IS NULL
            """)
        if new_loans_table:
            _seed_demo_loan(database)


def _create_loans_table(database):
    database.execute("""
        CREATE TABLE loans (
            loan_id INTEGER PRIMARY KEY,
            card_id TEXT NOT NULL REFERENCES registered_cards (card_id),
            item_id INTEGER NOT NULL REFERENCES equipment (item_id),
            borrowed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            returned_at TEXT
        )
    """)


def _seed_demo_loan(database):
    demo_item = database.execute(
        "SELECT item_id FROM equipment WHERE item_id = 1 AND name = 'Basketball'"
    ).fetchone()
    if demo_item is None:
        return

    # Add a pre-existing demo loan only for a newly inserted demo card.
    demo_card_id = "20260002"
    inserted = database.execute(
        "INSERT INTO registered_cards (card_id) VALUES (?) ON CONFLICT (card_id) DO NOTHING",
        (demo_card_id,),
    )
    if inserted.rowcount == 1:
        record_loan(database, demo_card_id, demo_item[0])
