"""SQLite storage for test cards, equipment availability, loans, and reservations."""

import secrets
import sqlite3
from collections import Counter
from contextlib import closing, contextmanager
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

ALLOWED_RESERVATION_MINUTES = (5, 10, 15, 20)
DEFAULT_RESERVATION_MINUTES = 10
PICKUP_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
PICKUP_CODE_LENGTH = 6


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


class ActiveReservationExists(Exception):
    """The card already has an active reservation."""


class ReservationNotFound(Exception):
    """The requested reservation or pickup code does not exist."""


class ReservationStateError(Exception):
    """The reservation is not in an active state."""


class InvalidReservationDuration(Exception):
    """The requested reservation hold duration is not allowed."""


class InvalidPassword(Exception):
    """The supplied current password does not match the registered card."""


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


def _generate_pickup_code():
    """Return a 6-character unambiguous uppercase pickup code."""
    return "".join(secrets.choice(PICKUP_CODE_ALPHABET) for _ in range(PICKUP_CODE_LENGTH))


def _expire_overdue_reservations(database):
    """Mark overdue active reservations as expired and restore stock in the current write tx."""
    overdue = database.execute("""
        SELECT reservation_id, item_id
        FROM reservations
        WHERE status = 'active' AND expires_at <= CURRENT_TIMESTAMP
    """).fetchall()
    if not overdue:
        return 0

    reservation_ids = [row["reservation_id"] for row in overdue]
    placeholders = ",".join("?" for _ in reservation_ids)
    database.execute(f"""
        UPDATE reservations
        SET status = 'expired', resolved_at = CURRENT_TIMESTAMP
        WHERE reservation_id IN ({placeholders}) AND status = 'active'
    """, reservation_ids)

    counts_by_item = Counter(row["item_id"] for row in overdue)
    for item_id, count in counts_by_item.items():
        database.execute(
            "UPDATE equipment SET available_quantity = available_quantity + ? WHERE item_id = ?",
            (count, item_id),
        )
    return len(overdue)


def _expire_overdue_if_needed(database):
    """Lazily expire overdue reservations only when at least one overdue active row exists."""
    has_overdue = database.execute("""
        SELECT 1 FROM reservations
        WHERE status = 'active' AND expires_at <= CURRENT_TIMESTAMP
        LIMIT 1
    """).fetchone()
    if has_overdue is None:
        return
    with database:
        database.execute("BEGIN IMMEDIATE")
        _expire_overdue_reservations(database)


def borrow_equipment(database_path, card_id, item_id):
    """Create the loan and reduce available stock in one transaction."""
    with _open_database(database_path) as database, database:
        database.execute("BEGIN IMMEDIATE")
        _expire_overdue_reservations(database)

        registered = database.execute(
            "SELECT 1 FROM registered_cards WHERE card_id = ?", (card_id,)
        ).fetchone()
        if registered is None:
            raise CardNotRegistered("This test card ID is not registered.")

        active_reservation = database.execute(
            "SELECT 1 FROM reservations WHERE card_id = ? AND status = 'active'", (card_id,)
        ).fetchone()
        if active_reservation is not None:
            raise ActiveReservationExists(
                "This card has an active reservation. Claim it with your pickup code or cancel it first."
            )

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


def find_active_reservation(database_path, card_id):
    """Return the active reservation for a registered card, or None."""
    with _open_database(database_path) as database:
        _expire_overdue_if_needed(database)
        row = database.execute("""
            SELECT reservations.reservation_id, reservations.card_id, reservations.item_id,
                   equipment.name AS item_name, reservations.pickup_code, reservations.status,
                   reservations.reserved_at, reservations.expires_at, reservations.resolved_at,
                   equipment.available_quantity
            FROM reservations
            JOIN equipment ON equipment.item_id = reservations.item_id
            WHERE reservations.card_id = ? AND reservations.status = 'active'
            LIMIT 1
        """, (card_id,)).fetchone()
        return dict(row) if row is not None else None


def create_reservation(database_path, card_id, item_id, duration_minutes=DEFAULT_RESERVATION_MINUTES):
    """Reserve one unit of equipment with a unique pickup code and expiry timestamp."""
    if type(duration_minutes) is not int or duration_minutes not in ALLOWED_RESERVATION_MINUTES:
        raise InvalidReservationDuration("Reservation duration must be 5, 10, 15, or 20 minutes.")

    with _open_database(database_path) as database, database:
        database.execute("BEGIN IMMEDIATE")
        _expire_overdue_reservations(database)

        registered = database.execute(
            "SELECT 1 FROM registered_cards WHERE card_id = ?", (card_id,)
        ).fetchone()
        if registered is None:
            raise CardNotRegistered("This test card ID is not registered.")

        active_loan = database.execute(
            "SELECT 1 FROM loans WHERE card_id = ? AND returned_at IS NULL", (card_id,)
        ).fetchone()
        if active_loan is not None:
            raise ActiveLoanExists("Return the current equipment before reserving another item.")

        active_reservation = database.execute(
            "SELECT 1 FROM reservations WHERE card_id = ? AND status = 'active'", (card_id,)
        ).fetchone()
        if active_reservation is not None:
            raise ActiveReservationExists("This card already has an active reservation.")

        item = database.execute(
            "SELECT available_quantity FROM equipment WHERE item_id = ?", (item_id,)
        ).fetchone()
        if item is None:
            raise EquipmentNotFound("This equipment item does not exist.")
        if item[0] == 0:
            raise EquipmentUnavailable("This item is out of stock.")

        stock = database.execute("""
            UPDATE equipment SET available_quantity = available_quantity - 1
            WHERE item_id = ? AND available_quantity > 0
        """, (item_id,))
        if stock.rowcount != 1:
            raise EquipmentUnavailable("This item is out of stock.")

        duration_modifier = f"+{duration_minutes} minutes"
        reservation_id = None
        for _ in range(5):
            pickup_code = _generate_pickup_code()
            try:
                cursor = database.execute("""
                    INSERT INTO reservations (card_id, item_id, pickup_code, expires_at)
                    VALUES (?, ?, ?, datetime('now', ?))
                """, (card_id, item_id, pickup_code, duration_modifier))
                reservation_id = cursor.lastrowid
                break
            except sqlite3.IntegrityError as error:
                message = str(error)
                if "pickup_code" in message:
                    continue
                raise ActiveReservationExists("This card already has an active reservation.") from error

        if reservation_id is None:
            raise sqlite3.IntegrityError("Unable to generate a unique pickup code.")

        return _read_reservation_details(database, reservation_id)


def claim_reservation(database_path, pickup_code):
    """Convert an active reservation into an active loan by its pickup code."""
    normalized_code = pickup_code.strip().upper()
    with _open_database(database_path) as database, database:
        database.execute("BEGIN IMMEDIATE")
        _expire_overdue_reservations(database)

        reservation = database.execute("""
            SELECT reservation_id, card_id, item_id, status
            FROM reservations
            WHERE pickup_code = ?
        """, (normalized_code,)).fetchone()
        if reservation is None:
            raise ReservationNotFound("Invalid pickup code.")

        status = reservation["status"]
        if status == "claimed":
            raise ReservationStateError("This pickup code has already been used.")
        if status == "expired":
            raise ReservationStateError("This reservation has expired and the item was returned to stock.")
        if status == "cancelled":
            raise ReservationStateError("This reservation has been cancelled.")
        if status != "active":
            raise ReservationStateError("This reservation is no longer active.")

        updated = database.execute("""
            UPDATE reservations
            SET status = 'claimed', resolved_at = CURRENT_TIMESTAMP
            WHERE reservation_id = ? AND status = 'active'
        """, (reservation["reservation_id"],))
        if updated.rowcount != 1:
            raise ReservationStateError("This reservation is no longer active.")

        loan_id = record_loan(database, reservation["card_id"], reservation["item_id"])
        return {
            "loan": _read_loan_details(database, loan_id),
            "reservation": _read_reservation_details(database, reservation["reservation_id"]),
        }


def cancel_reservation(database_path, card_id=None, reservation_id=None, pickup_code=None):
    """Cancel an active reservation and restore its held unit to stock."""
    with _open_database(database_path) as database, database:
        database.execute("BEGIN IMMEDIATE")
        _expire_overdue_reservations(database)

        if pickup_code is not None:
            normalized_code = pickup_code.strip().upper()
            reservation = database.execute("""
                SELECT reservation_id, item_id, status
                FROM reservations
                WHERE pickup_code = ?
            """, (normalized_code,)).fetchone()
        else:
            reservation = database.execute("""
                SELECT reservation_id, item_id, status
                FROM reservations
                WHERE reservation_id = ? AND card_id = ?
            """, (reservation_id, card_id)).fetchone()

        if reservation is None:
            raise ReservationNotFound("Reservation not found.")

        status = reservation["status"]
        if status != "active":
            raise ReservationStateError(f"This reservation is already {status} and cannot be cancelled.")

        updated = database.execute("""
            UPDATE reservations
            SET status = 'cancelled', resolved_at = CURRENT_TIMESTAMP
            WHERE reservation_id = ? AND status = 'active'
        """, (reservation["reservation_id"],))
        if updated.rowcount != 1:
            raise ReservationStateError("This reservation is no longer active.")

        database.execute("""
            UPDATE equipment SET available_quantity = available_quantity + 1
            WHERE item_id = ?
        """, (reservation["item_id"],))

        return _read_reservation_details(database, reservation["reservation_id"])


def _read_loan_details(database, loan_id):
    return dict(database.execute("""
        SELECT loans.loan_id, loans.item_id, equipment.name AS item_name,
               loans.borrowed_at, loans.returned_at, equipment.available_quantity
        FROM loans JOIN equipment ON equipment.item_id = loans.item_id
        WHERE loans.loan_id = ?
    """, (loan_id,)).fetchone())


def _read_reservation_details(database, reservation_id):
    return dict(database.execute("""
        SELECT reservations.reservation_id, reservations.card_id, reservations.item_id,
               equipment.name AS item_name, reservations.pickup_code, reservations.status,
               reservations.reserved_at, reservations.expires_at, reservations.resolved_at,
               equipment.available_quantity
        FROM reservations
        JOIN equipment ON equipment.item_id = reservations.item_id
        WHERE reservations.reservation_id = ?
    """, (reservation_id,)).fetchone())


def _hash_password(password):
    return generate_password_hash(password, method="pbkdf2:sha256:100000")


def _verify_card_password(row, password):
    stored_hash = row["password_hash"]
    if stored_hash:
        return check_password_hash(stored_hash, password)
    return password == row["card_id"][-4:]


def authenticate_card(database_path, card_id, password):
    """Verify a registered card ID and password, returning loan status row, False on bad password, or None."""
    with _open_database(database_path) as database:
        _expire_overdue_if_needed(database)
        row = database.execute(
            "SELECT card_id, password_hash FROM registered_cards WHERE card_id = ?",
            (card_id,),
        ).fetchone()
        if row is None:
            return None
        if not _verify_card_password(row, password):
            return False
        return database.execute("""
            SELECT cards.card_id, loans.loan_id, loans.item_id, equipment.name AS item_name
            FROM registered_cards AS cards
            LEFT JOIN loans ON loans.card_id = cards.card_id AND loans.returned_at IS NULL
            LEFT JOIN equipment ON equipment.item_id = loans.item_id
            WHERE cards.card_id = ?
            ORDER BY loans.loan_id DESC
            LIMIT 1
        """, (card_id,)).fetchone()


def change_card_password(database_path, card_id, current_password, new_password):
    """Verify the current password and update password_hash for an existing registered card."""
    with _open_database(database_path) as database, database:
        database.execute("BEGIN IMMEDIATE")
        row = database.execute(
            "SELECT card_id, password_hash FROM registered_cards WHERE card_id = ?",
            (card_id,),
        ).fetchone()
        if row is None:
            raise CardNotRegistered("This test card ID is not registered.")
        if not _verify_card_password(row, current_password):
            raise InvalidPassword("Current password is incorrect.")
        database.execute(
            "UPDATE registered_cards SET password_hash = ? WHERE card_id = ?",
            (_hash_password(new_password), card_id),
        )


def find_card_loan_status(database_path, card_id):
    """Find a registered card and any outstanding loan for it."""
    with _open_database(database_path) as database:
        _expire_overdue_if_needed(database)
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
        _expire_overdue_if_needed(database)
        return _read_equipment(database)


def read_staff_overview(database_path):
    """Read equipment and loan history from the same SQLite snapshot."""
    with _open_database(database_path) as database, database:
        _expire_overdue_if_needed(database)
        database.execute("BEGIN")
        equipment = _read_equipment(database)
        loans = database.execute("""
            SELECT loans.loan_id, loans.card_id, equipment.name AS item_name,
                   loans.borrowed_at, loans.returned_at
            FROM loans JOIN equipment ON equipment.item_id = loans.item_id
            ORDER BY loans.borrowed_at DESC, loans.loan_id DESC
        """).fetchall()
        return equipment, loans


def read_staff_dashboard(database_path):
    """Read equipment, loan history (with due/overdue), and reservations from one snapshot."""
    with _open_database(database_path) as database, database:
        _expire_overdue_if_needed(database)
        database.execute("BEGIN")
        equipment = _read_equipment(database)
        loans = database.execute("""
            SELECT loans.loan_id, loans.card_id, equipment.name AS item_name,
                   loans.borrowed_at, loans.returned_at,
                   datetime(loans.borrowed_at, '+2 hours') AS due_at,
                   CASE
                       WHEN loans.returned_at IS NULL
                            AND datetime(loans.borrowed_at, '+2 hours') < CURRENT_TIMESTAMP
                       THEN 1
                       ELSE 0
                   END AS is_overdue
            FROM loans JOIN equipment ON equipment.item_id = loans.item_id
            ORDER BY loans.borrowed_at DESC, loans.loan_id DESC
        """).fetchall()
        reservations = database.execute("""
            SELECT reservations.reservation_id, reservations.card_id, reservations.item_id,
                   equipment.name AS item_name, reservations.pickup_code, reservations.status,
                   reservations.reserved_at, reservations.expires_at, reservations.resolved_at
            FROM reservations
            JOIN equipment ON equipment.item_id = reservations.item_id
            ORDER BY CASE WHEN reservations.status = 'active' THEN 0 ELSE 1 END,
                     reservations.reserved_at DESC,
                     reservations.reservation_id DESC
        """).fetchall()
        return equipment, loans, reservations


def _read_equipment(database):
    return database.execute(
        "SELECT item_id, name, available_quantity FROM equipment ORDER BY item_id"
    ).fetchall()


@contextmanager
def _open_database(database_path):
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as database:
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA busy_timeout = 5000")
        database.execute("PRAGMA journal_mode = WAL")
        database.execute("PRAGMA foreign_keys = ON")
        _initialize_database(database)
        yield database


def _schema_names(database):
    return {
        name for (name,) in database.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')"
        )
    }


def _has_column(database, table_name, column_name):
    rows = database.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row["name"] == column_name for row in rows)


def _initialize_database(database):
    required = {
        "registered_cards",
        "equipment",
        "loans",
        "unique_active_loan_per_card",
        "reservations",
        "unique_active_reservation_per_card",
    }
    if required.issubset(_schema_names(database)) and _has_column(database, "registered_cards", "password_hash"):
        return

    # Apply schema changes and demo seeds together while preserving existing rows.
    with database:
        database.execute("BEGIN IMMEDIATE")
        schema = _schema_names(database)
        if "registered_cards" not in schema:
            database.execute(
                "CREATE TABLE registered_cards (card_id TEXT NOT NULL PRIMARY KEY, password_hash TEXT)"
            )
            database.execute(
                "INSERT INTO registered_cards (card_id, password_hash) VALUES (?, ?)",
                ("20260001", _hash_password("0001")),
            )
        elif not _has_column(database, "registered_cards", "password_hash"):
            database.execute("ALTER TABLE registered_cards ADD COLUMN password_hash TEXT")
            if _has_column(database, "registered_cards", "pin_hash"):
                database.execute(
                    "UPDATE registered_cards SET password_hash = pin_hash WHERE password_hash IS NULL AND pin_hash IS NOT NULL"
                )

        missing_passwords = database.execute(
            "SELECT card_id FROM registered_cards WHERE password_hash IS NULL"
        ).fetchall()
        for row in missing_passwords:
            database.execute(
                "UPDATE registered_cards SET password_hash = ? WHERE card_id = ?",
                (_hash_password(row["card_id"][-4:]), row["card_id"]),
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
        if "reservations" not in schema:
            _create_reservations_table(database)
        if "unique_active_reservation_per_card" not in schema:
            database.execute("""
                CREATE UNIQUE INDEX unique_active_reservation_per_card
                ON reservations (card_id) WHERE status = 'active'
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


def _create_reservations_table(database):
    database.execute("""
        CREATE TABLE reservations (
            reservation_id INTEGER PRIMARY KEY,
            card_id TEXT NOT NULL REFERENCES registered_cards (card_id),
            item_id INTEGER NOT NULL REFERENCES equipment (item_id),
            pickup_code TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL CHECK (status IN ('active', 'claimed', 'cancelled', 'expired')) DEFAULT 'active',
            reserved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            resolved_at TEXT
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
        "INSERT INTO registered_cards (card_id, password_hash) VALUES (?, ?) ON CONFLICT (card_id) DO NOTHING",
        (demo_card_id, _hash_password("0002")),
    )
    if inserted.rowcount == 1:
        record_loan(database, demo_card_id, demo_item[0])
