"""SQLite storage for test cards, equipment availability, and loans."""

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path


class ActiveLoanExists(Exception):
    """The card already has an outstanding loan."""


class NoActiveLoan(Exception):
    """The requested loan is no longer active for this card."""


class CardNotRegistered(Exception):
    """The test card does not exist."""


class EquipmentNotFound(Exception):
    """The requested equipment does not exist."""


class EquipmentUnavailable(Exception):
    """No units of the requested equipment are available."""


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


def borrow_equipment(database_path, card_id, item_id):
    """Create the loan and reduce available stock in one transaction."""
    with _open_database(database_path) as database, database:
        database.execute("BEGIN IMMEDIATE")
        registered = database.execute(
            "SELECT 1 FROM registered_cards WHERE card_id = ?", (card_id,)
        ).fetchone()
        if registered is None:
            raise CardNotRegistered("This test card ID is not registered.")

        item = database.execute(
            "SELECT available_quantity FROM equipment WHERE item_id = ?", (item_id,)
        ).fetchone()
        if item is None:
            raise EquipmentNotFound("This equipment item does not exist.")
        if item[0] == 0:
            raise EquipmentUnavailable("This item is out of stock.")

        loan_id = record_loan(database, card_id, item_id)
        stock = database.execute("""
            UPDATE equipment SET available_quantity = available_quantity - 1
            WHERE item_id = ? AND available_quantity > 0
        """, (item_id,))
        if stock.rowcount != 1:
            raise EquipmentUnavailable("This item is out of stock.")

        return _read_loan_details(database, loan_id)


def return_equipment(database_path, card_id, loan_id):
    """Close the requested active loan and restore its stock in one transaction."""
    with _open_database(database_path) as database, database:
        database.execute("BEGIN IMMEDIATE")
        returned = database.execute("""
            UPDATE loans SET returned_at = CURRENT_TIMESTAMP
            WHERE loan_id = ? AND card_id = ? AND returned_at IS NULL
        """, (loan_id, card_id))
        if returned.rowcount != 1:
            raise NoActiveLoan("This loan is no longer active for this card. Verify the card again.")

        stock = database.execute("""
            UPDATE equipment SET available_quantity = available_quantity + 1
            WHERE item_id = (SELECT item_id FROM loans WHERE loan_id = ?)
        """, (loan_id,))
        if stock.rowcount != 1:
            raise sqlite3.IntegrityError("Unable to restore stock for the returned loan.")

        return _read_loan_details(database, loan_id)


def _read_loan_details(database, loan_id):
    return dict(database.execute("""
        SELECT loans.loan_id, loans.item_id, equipment.name AS item_name,
               loans.borrowed_at, loans.returned_at, equipment.available_quantity
        FROM loans JOIN equipment ON equipment.item_id = loans.item_id
        WHERE loans.loan_id = ?
    """, (loan_id,)).fetchone())


def find_card_loan_status(database_path, card_id):
    """Find a registered card and any outstanding loan for it."""
    with _open_database(database_path) as database:
        return database.execute("""
            SELECT cards.card_id, loans.loan_id, loans.item_id, equipment.name AS item_name
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
        return database.execute(
            "SELECT item_id, name, available_quantity FROM equipment ORDER BY item_id"
        ).fetchall()


@contextmanager
def _open_database(database_path):
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as database:
        database.row_factory = sqlite3.Row
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
