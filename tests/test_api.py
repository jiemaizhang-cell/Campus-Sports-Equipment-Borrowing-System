import re
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch

from app import app
from database import ActiveLoanExists, record_loan


class PrototypeAPITestCase(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.database_path = Path(directory.name) / "instance" / "campus.db"
        config = patch.dict(app.config, DATABASE=self.database_path)
        config.start()
        self.addCleanup(config.stop)
        self.client = app.test_client()

    def login(self, card_id="20260001", password=None, client=None):
        target = client or self.client
        normalized = card_id.strip() if isinstance(card_id, str) else card_id
        resolved_pw = password if password is not None else (normalized[-4:] if isinstance(normalized, str) else "")
        return target.post("/api/login", json={"card_id": card_id, "password": resolved_pw})

    def database_state(self):
        with closing(sqlite3.connect(self.database_path)) as database:
            stock = database.execute(
                "SELECT item_id, available_quantity FROM equipment ORDER BY item_id"
            ).fetchall()
            loans = database.execute("SELECT * FROM loans ORDER BY loan_id").fetchall()
        return stock, loans

    def concurrent_posts(self, path, payloads, login_card_id=None):
        start = Barrier(len(payloads))

        def attempt(payload):
            client = app.test_client()
            if login_card_id is not None:
                self.login(login_card_id, client=client)
            start.wait(timeout=5)
            return client.post(path, json=payload)

        with ThreadPoolExecutor(max_workers=len(payloads)) as workers:
            return list(workers.map(attempt, payloads))

    @contextmanager
    def simulate_write_failure(self, event, table):
        with closing(sqlite3.connect(self.database_path)) as database, database:
            database.execute(f"""
                CREATE TRIGGER fail_test_write BEFORE {event} ON {table}
                BEGIN SELECT RAISE(ABORT, 'test write failure'); END
            """)
        try:
            yield
        finally:
            with closing(sqlite3.connect(self.database_path)) as database, database:
                database.execute("DROP TRIGGER fail_test_write")


class CardAPIIntegrationTests(PrototypeAPITestCase):
    def test_home_page_requires_login_and_separates_systems(self):
        unauth = self.client.get("/")
        self.assertEqual(unauth.status_code, 302)
        self.assertIn("/login", unauth.headers["Location"])

        login_page = self.client.get("/login")
        self.assertEqual(login_page.status_code, 200)
        self.assertIn(b"Student Card ID", login_page.data)
        self.assertIn(b"Password", login_page.data)
        self.assertNotIn(b'href="/staff"', login_page.data)
        self.assertNotIn(b'href="/counter"', login_page.data)

        self.assertEqual(self.login("20260001", "0001").status_code, 200)
        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn(b"20260001", home.data)
        self.assertIn(b'id="change-password-btn"', home.data)
        self.assertNotIn(b'href="/staff"', home.data)
        self.assertNotIn(b'href="/counter"', home.data)

    def test_valid_card(self):
        response = self.client.post("/api/validate-card", json={"card_id": "20260001"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["card_id"], "20260001")

    def test_invalid_card(self):
        response = self.client.post("/api/validate-card", json={"card_id": "ABC123"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["valid"])

    def test_missing_field(self):
        response = self.client.post("/api/validate-card", json={})
        self.assertEqual(response.status_code, 400)

    def test_non_json_request(self):
        response = self.client.post("/api/validate-card", data="not json")
        self.assertEqual(response.status_code, 400)


class CardVerificationTests(PrototypeAPITestCase):
    def test_login_page_uses_login_endpoint_and_rejects_bad_password(self):
        response = self.client.get("/login")
        self.assertIn(b'action="/api/login"', response.data)

        bad_pw = self.login("20260001", "wrongpass")
        self.assertEqual(bad_pw.status_code, 401)
        self.assertFalse(bad_pw.get_json()["valid"])

        unknown = self.login("20260099", "0099")
        self.assertEqual(unknown.status_code, 401)

        ok = self.login(" 20260001 ", "0001")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.get_json()["card_id"], "20260001")

        out = self.client.post("/logout")
        self.assertEqual(out.status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_change_password_flow_and_no_account_creation(self):
        # No registration endpoint exists
        for path in ("/register", "/signup", "/api/register"):
            self.assertEqual(self.client.post(path, json={"card_id": "20260099", "password": "secret12"}).status_code, 404)

        # Must be signed in to change password
        anon_res = self.client.post("/api/change-password", json={
            "current_password": "0001",
            "new_password": "Campus#2026",
            "confirm_password": "Campus#2026",
        })
        self.assertEqual(anon_res.status_code, 401)

        self.login("20260001", "0001")

        # Cannot target another card
        cross = self.client.post("/api/change-password", json={
            "card_id": "20260002",
            "current_password": "0002",
            "new_password": "Campus#2026",
            "confirm_password": "Campus#2026",
        })
        self.assertEqual(cross.status_code, 403)

        # Validation checks: wrong current, too short, blank spaces, mismatch, same password
        self.assertEqual(self.client.post("/api/change-password", json={
            "current_password": "wrong",
            "new_password": "Campus#2026",
            "confirm_password": "Campus#2026",
        }).status_code, 401)
        self.assertEqual(self.client.post("/api/change-password", json={
            "current_password": "0001",
            "new_password": "123",
            "confirm_password": "123",
        }).status_code, 400)
        self.assertEqual(self.client.post("/api/change-password", json={
            "current_password": "0001",
            "new_password": "      ",
            "confirm_password": "      ",
        }).status_code, 400)
        self.assertEqual(self.client.post("/api/change-password", json={
            "current_password": "0001",
            "new_password": "Campus#2026",
            "confirm_password": "Different#1",
        }).status_code, 400)
        self.assertEqual(self.client.post("/api/change-password", json={
            "current_password": "0001",
            "new_password": "0001",
            "confirm_password": "0001",
        }).status_code, 400)

        # Valid change
        changed = self.client.post("/api/change-password", json={
            "current_password": "0001",
            "new_password": "Campus#2026",
            "confirm_password": "Campus#2026",
        })
        self.assertEqual(changed.status_code, 200)

        self.client.post("/logout")
        self.assertEqual(self.login("20260001", "0001").status_code, 401)
        self.assertEqual(self.login("20260001", "Campus#2026").status_code, 200)

    def test_accepts_registered_card_after_normalization(self):
        response = self.client.post("/api/verify-card", json={"card_id": " 20260001 "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "valid": True,
            "card_id": "20260001",
            "message": "Test card verified.",
            "active_loan": None,
        })

    def test_rejects_unregistered_card(self):
        response = self.client.post("/api/verify-card", json={"card_id": "20260099"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {
            "valid": False,
            "message": "This test card ID is not registered.",
        })

    def test_keeps_format_errors_from_b1(self):
        for card_id in ("", "ABC123"):
            with self.subTest(card_id=card_id):
                b1 = self.client.post("/api/validate-card", json={"card_id": card_id})
                b2 = self.client.post("/api/verify-card", json={"card_id": card_id})
                self.assertEqual(b2.status_code, 400)
                self.assertEqual(b2.get_json(), b1.get_json())
        self.assertFalse(self.database_path.exists())

    def test_looks_up_current_database_registrations(self):
        self.client.post("/api/verify-card", json={"card_id": "20260001"})
        with closing(sqlite3.connect(self.database_path)) as database, database:
            database.execute(
                "UPDATE registered_cards SET card_id = ? WHERE card_id = ?",
                ("02026001", "20260001"),
            )

        registered = self.client.post("/api/verify-card", json={"card_id": "02026001"})
        removed = self.client.post("/api/verify-card", json={"card_id": "20260001"})
        self.assertEqual(registered.status_code, 200)
        self.assertEqual(registered.get_json()["card_id"], "02026001")
        self.assertEqual(removed.status_code, 404)


class EquipmentAvailabilityTests(PrototypeAPITestCase):
    def setUp(self):
        super().setUp()
        self.login("20260001", "0001")

    def test_home_displays_each_demo_item_with_its_quantity(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        for name, quantity, state in (
            ("Basketball", 5, "Available"),
            ("Football", 3, "Available"),
            ("Badminton racket", 0, "Unavailable"),
        ):
            with self.subTest(equipment=name):
                self.assertRegex(
                    html,
                    rf'{name}</th>\s*<td>{quantity}</td>\s*'
                    rf'<td class="stock-{state.lower()}">{state}</td>',
                )

    def test_home_reload_reflects_current_stock(self):
        self.client.get("/")
        with closing(sqlite3.connect(self.database_path)) as database, database:
            database.execute(
                "UPDATE equipment SET available_quantity = ? WHERE item_id = ?", (0, 1)
            )
            database.execute(
                "UPDATE equipment SET available_quantity = ? WHERE item_id = ?", (4, 3)
            )

        response = self.client.get("/")
        html = response.get_data(as_text=True)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertRegex(html, r'Basketball</th>\s*<td>0</td>\s*<td class="stock-unavailable">')
        self.assertRegex(html, r'Badminton racket</th>\s*<td>4</td>\s*<td class="stock-available">')

    def test_initializes_equipment_in_an_existing_card_database(self):
        temp_dir = TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        legacy_db = Path(temp_dir.name) / "instance" / "campus.db"
        legacy_db.parent.mkdir()
        with closing(sqlite3.connect(legacy_db)) as database, database:
            database.execute("CREATE TABLE registered_cards (card_id TEXT NOT NULL PRIMARY KEY)")
            database.execute("INSERT INTO registered_cards VALUES (?)", ("02026001",))

        with patch.dict(app.config, DATABASE=legacy_db):
            self.login("02026001", "6001")
            self.assertIn(b"Badminton racket", self.client.get("/").data)
            registered = self.client.post("/api/verify-card", json={"card_id": "02026001"})
            demo_card = self.client.post("/api/verify-card", json={"card_id": "20260001"})
            self.assertEqual(registered.status_code, 200)
            self.assertEqual(demo_card.status_code, 404)


class ActiveLoanTests(PrototypeAPITestCase):
    def test_verified_card_with_an_active_loan_returns_the_item_and_status(self):
        response = self.client.post("/api/verify-card", json={"card_id": "20260002"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["active_loan"], {
            "loan_id": "1",
            "item_id": "1",
            "item_name": "Basketball",
            "status": "active",
        })

    def test_returned_loan_is_excluded_on_next_verification(self):
        self.client.post("/api/verify-card", json={"card_id": "20260002"})
        with closing(sqlite3.connect(self.database_path)) as database, database:
            database.execute("UPDATE loans SET returned_at = CURRENT_TIMESTAMP WHERE card_id = ?", ("20260002",))

        response = self.client.post("/api/verify-card", json={"card_id": "20260002"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["active_loan"])

    def test_migration_keeps_an_existing_demo_card_and_stock(self):
        self.login("20260001", "0001")
        with closing(sqlite3.connect(self.database_path)) as database, database:
            database.execute("DROP TABLE loans")
            database.execute("UPDATE equipment SET available_quantity = 2 WHERE item_id = 1")

        response = self.client.post("/api/verify-card", json={"card_id": "20260002"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["active_loan"])
        self.assertRegex(self.client.get("/").get_data(as_text=True), r"Basketball</th>\s*<td>2</td>")


class ActiveLoanLimitTests(PrototypeAPITestCase):
    def setUp(self):
        super().setUp()
        self.client.get("/staff")

    def test_duplicate_loan_rejection_rolls_back_inventory_changes(self):
        with closing(sqlite3.connect(self.database_path)) as database:
            stock_query = "SELECT item_id, available_quantity FROM equipment ORDER BY item_id"
            original_stock = database.execute(stock_query).fetchall()
            for item_id in (1, 2):
                with self.subTest(item_id=item_id), self.assertRaises(ActiveLoanExists), database:
                    database.execute("""
                        UPDATE equipment SET available_quantity = available_quantity - 1
                        WHERE item_id = ?
                    """, (item_id,))
                    record_loan(database, "20260002", item_id)

            self.assertEqual(database.execute(stock_query).fetchall(), original_stock)
            loans = database.execute("SELECT item_id FROM loans WHERE card_id = ?", ("20260002",))
            self.assertEqual(loans.fetchall(), [(1,)])

    def test_concurrent_loan_writes_leave_one_active_loan(self):
        start = Barrier(2)

        def attempt_loan(item_id):
            with closing(sqlite3.connect(self.database_path)) as database:
                start.wait(timeout=5)
                try:
                    with database:
                        return record_loan(database, "20260001", item_id)
                except ActiveLoanExists:
                    return None

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(attempt_loan, (1, 2)))

        successful_loans = [loan_id for loan_id in results if loan_id is not None]
        self.assertEqual(len(successful_loans), 1)
        with closing(sqlite3.connect(self.database_path)) as database:
            active_loans = database.execute("""
                SELECT loan_id FROM loans WHERE card_id = ? AND returned_at IS NULL
            """, ("20260001",)).fetchall()
            self.assertEqual(active_loans, [(successful_loans[0],)])

    def test_a_returned_loan_allows_another_loan(self):
        with closing(sqlite3.connect(self.database_path)) as database, database:
            database.execute("""
                UPDATE loans SET returned_at = CURRENT_TIMESTAMP WHERE card_id = ?
            """, ("20260002",))
            record_loan(database, "20260002", 2)
            loans = database.execute("""
                SELECT item_id, returned_at IS NULL FROM loans WHERE card_id = ? ORDER BY loan_id
            """, ("20260002",))
            self.assertEqual(loans.fetchall(), [(1, 0), (2, 1)])

    def test_existing_database_gets_the_unique_index_without_changing_loans(self):
        with closing(sqlite3.connect(self.database_path)) as database, database:
            original_loans = database.execute("SELECT * FROM loans").fetchall()
            database.execute("DROP INDEX unique_active_loan_per_card")

        response = self.client.post("/api/verify-card", json={"card_id": "20260002"})
        self.assertEqual(response.status_code, 200)
        with closing(sqlite3.connect(self.database_path)) as database:
            with self.assertRaises(sqlite3.IntegrityError), database:
                database.execute("INSERT INTO loans (card_id, item_id) VALUES (?, ?)", ("20260002", 2))
            self.assertEqual(database.execute("SELECT * FROM loans").fetchall(), original_loans)


class BorrowEquipmentTests(PrototypeAPITestCase):
    def setUp(self):
        super().setUp()
        self.login("20260001", "0001")

    def borrow(self, item_id, card_id="20260001"):
        if card_id and card_id.strip() in ("20260001", "20260002"):
            self.login(card_id)
        return self.client.post("/api/borrow", json={"card_id": card_id, "item_id": item_id})

    def test_borrow_creates_a_timestamped_loan_and_decreases_stock(self):
        _, original_loans = self.database_state()
        response = self.borrow("2", " 20260001 ")
        self.assertEqual(response.status_code, 201)
        loan = response.get_json()["loan"]
        self.assertEqual(loan["item_id"], 2)
        self.assertEqual(loan["available_quantity"], 2)
        self.assertRegex(loan["borrowed_at"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

        stock, loans = self.database_state()
        self.assertEqual(stock, [(1, 5), (2, 2), (3, 0)])
        self.assertEqual(loans, original_loans + [
            (loan["loan_id"], "20260001", 2, loan["borrowed_at"], None),
        ])
        verified = self.client.post("/api/verify-card", json={"card_id": "20260001"})
        self.assertEqual(verified.get_json()["active_loan"], {
            "loan_id": str(loan["loan_id"]),
            "item_id": "2",
            "item_name": "Football",
            "status": "active",
        })

    def test_rejects_out_of_stock_without_leaving_a_loan(self):
        original = self.database_state()
        response = self.borrow(3)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["message"], "This item is out of stock.")
        self.assertEqual(self.database_state(), original)

    def test_rejects_missing_or_invalid_card_and_equipment(self):
        original = self.database_state()
        for card_id, item_id, status in (
            ("", 1, 400), ("20260099", 1, 403), ("20260001", 99, 404),
            ("20260001", True, 400), ("20260001", 2**63, 400), ("20260001", None, 400),
        ):
            with self.subTest(card_id=card_id, item_id=item_id):
                self.assertEqual(self.borrow(item_id, card_id).status_code, status)
        self.assertEqual(self.database_state(), original)

    def test_rejects_same_item_or_another_item_for_a_card_with_an_active_loan(self):
        original = self.database_state()
        for item_id in (1, 2):
            with self.subTest(item_id=item_id):
                response = self.borrow(item_id, "20260002")
                self.assertEqual(response.status_code, 409)
                self.assertEqual(
                    response.get_json()["message"],
                    "Return the current equipment before borrowing another item.",
                )
        self.assertEqual(self.database_state(), original)

    def test_concurrent_http_requests_for_one_card_commit_one_loan(self):
        original_stock, original_loans = self.database_state()
        responses = self.concurrent_posts(
            "/api/borrow",
            [{"card_id": "20260001", "item_id": item_id} for item_id in (1, 2)],
            login_card_id="20260001",
        )

        self.assertEqual(sorted(response.status_code for response in responses), [201, 409])
        loan = next(response.get_json()["loan"] for response in responses if response.status_code == 201)
        stock, loans = self.database_state()
        self.assertEqual(stock, [
            (item_id, available - (item_id == loan["item_id"])) for item_id, available in original_stock
        ])
        self.assertEqual(loans, original_loans + [
            (loan["loan_id"], "20260001", loan["item_id"], loan["borrowed_at"], None),
        ])

    def test_rolls_back_if_either_database_write_fails(self):
        original = self.database_state()
        for event, table in (("INSERT", "loans"), ("UPDATE", "equipment")):
            with self.subTest(table=table), self.simulate_write_failure(event, table):
                with self.assertLogs(app.logger, level="ERROR"):
                    response = self.borrow(1)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(self.database_state(), original)


class ReturnEquipmentTests(PrototypeAPITestCase):
    def setUp(self):
        super().setUp()
        self.demo_loan_id = self.verify("20260002")["loan_id"]

    def verify(self, card_id):
        response = self.client.post("/api/verify-card", json={"card_id": card_id})
        self.assertEqual(response.status_code, 200)
        return response.get_json()["active_loan"]

    def return_loan(self, loan_id, card_id="20260002"):
        return self.client.post("/api/return", json={"card_id": card_id, "loan_id": loan_id})

    def test_borrow_return_verify_and_borrow_again(self):
        original_stock, _ = self.database_state()
        self.login("20260001", "0001")
        card = {"card_id": "20260001", "item_id": 2}
        borrow = self.client.post("/api/borrow", json=card)
        self.assertEqual(borrow.status_code, 201)
        active = self.verify(card["card_id"])
        self.assertEqual(active, borrow.get_json()["active_loan"])

        response = self.return_loan(active["loan_id"], " 20260001 ")
        self.assertEqual(response.status_code, 200)
        returned = response.get_json()["loan"]
        self.assertEqual(returned["available_quantity"], 3)
        self.assertRegex(returned["returned_at"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
        stock, loans = self.database_state()
        self.assertEqual(stock, original_stock)
        self.assertIn((returned["loan_id"], "20260001", 2, returned["borrowed_at"], returned["returned_at"]), loans)
        self.assertIsNone(self.verify(card["card_id"]))

        next_borrow = self.client.post("/api/borrow", json=card)
        self.assertEqual(next_borrow.status_code, 201)
        self.assertNotEqual(next_borrow.get_json()["active_loan"]["loan_id"], active["loan_id"])

    def test_repeated_return_cannot_close_a_newer_loan_or_increase_stock(self):
        self.assertEqual(self.return_loan(self.demo_loan_id).status_code, 200)
        after_return = self.database_state()
        self.assertEqual(self.return_loan(self.demo_loan_id).status_code, 409)
        self.assertEqual(self.database_state(), after_return)

        self.login("20260002", "0002")
        borrow = self.client.post("/api/borrow", json={"card_id": "20260002", "item_id": 2})
        self.assertEqual(borrow.status_code, 201)
        before_retry = self.database_state()
        self.assertEqual(self.return_loan(self.demo_loan_id).status_code, 409)
        self.assertEqual(self.database_state(), before_retry)
        self.assertEqual(self.verify("20260002"), borrow.get_json()["active_loan"])

    def test_concurrent_returns_restore_stock_only_once(self):
        payload = {"card_id": "20260002", "loan_id": self.demo_loan_id}
        responses = self.concurrent_posts("/api/return", [payload, payload])
        self.assertEqual(sorted(response.status_code for response in responses), [200, 409])
        stock, _ = self.database_state()
        self.assertEqual(stock, [(1, 6), (2, 3), (3, 0)])
        self.assertIsNone(self.verify("20260002"))

    def test_rejects_invalid_ids_and_a_loan_for_another_card(self):
        original = self.database_state()
        for loan_id, card_id, status in (
            (self.demo_loan_id, "20260001", 409), (self.demo_loan_id, "", 400),
            (True, "20260002", 400), (None, "20260002", 400), (2**63, "20260002", 400),
        ):
            with self.subTest(loan_id=loan_id, card_id=card_id):
                self.assertEqual(self.return_loan(loan_id, card_id).status_code, status)
        self.assertEqual(self.database_state(), original)

    def test_return_rolls_back_if_either_database_write_fails(self):
        original = self.database_state()
        for table in ("loans", "equipment"):
            with self.subTest(table=table), self.simulate_write_failure("UPDATE", table):
                with self.assertLogs(app.logger, level="ERROR"):
                    response = self.return_loan(self.demo_loan_id)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(self.database_state(), original)


class StaffViewTests(PrototypeAPITestCase):
    def row(self, html, row_id):
        match = re.search(rf'<tr id="{row_id}">(.*?)</tr>', html, re.DOTALL)
        self.assertIsNotNone(match, f"Missing staff table row {row_id}")
        return match.group(1)

    def test_staff_view_shows_current_inventory_and_an_existing_loan(self):
        response = self.client.get("/staff")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        html = response.get_data(as_text=True)
        self.assertNotIn('href="/"', html)
        self.assertNotIn('href="/login"', html)
        self.assertIn('href="/counter"', html)

        stock, loans = self.database_state()
        for item_id, quantity in stock:
            with self.subTest(item_id=item_id):
                self.assertIn(f"<td>{quantity}</td>", self.row(html, f"equipment-{item_id}"))
        loan_id, card_id, _, borrowed_at, _ = loans[0]
        loan_row = self.row(html, f"loan-{loan_id}")
        self.assertIn("Basketball</th>", loan_row)
        self.assertIn(f"<td>{card_id}</td>", loan_row)
        self.assertIn("<td>Active</td>", loan_row)
        self.assertIn(f">{borrowed_at}</time>", loan_row)

    def test_staff_view_reflects_successful_borrow_and_return(self):
        card_id = "20260001"
        self.login(card_id, "0001")
        borrow = self.client.post("/api/borrow", json={"card_id": card_id, "item_id": 2})
        self.assertEqual(borrow.status_code, 201)
        loan = borrow.get_json()["loan"]
        row_id = f"loan-{loan['loan_id']}"
        active_html = self.client.get("/staff").get_data(as_text=True)
        active_row = self.row(active_html, row_id)
        self.assertIn("Football</th>", active_row)
        self.assertIn("<td>Active</td>", active_row)
        self.assertIn(f">{loan['borrowed_at']}</time>", active_row)
        self.assertIn("<td>2</td>", self.row(active_html, "equipment-2"))

        rejected = self.client.post("/api/borrow", json={"card_id": card_id, "item_id": 1})
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(self.client.get("/staff").get_data(as_text=True), active_html)

        returned = self.client.post("/api/return", json={"card_id": card_id, "loan_id": loan["loan_id"]})
        self.assertEqual(returned.status_code, 200)
        staff_html = self.client.get("/staff").get_data(as_text=True)
        returned_row = self.row(staff_html, row_id)
        self.assertIn("<td>Returned</td>", returned_row)
        stock, loans = self.database_state()
        current_loan = next(record for record in loans if record[0] == loan["loan_id"])
        self.assertIn(f">{current_loan[3]}</time>", returned_row)
        self.assertIn(f">{current_loan[4]}</time>", returned_row)
        self.assertIn("<td>Active</td>", self.row(staff_html, "loan-1"))
        self.assertIn(f"<td>{dict(stock)[2]}</td>", self.row(staff_html, "equipment-2"))
        self.assertEqual(dict(stock)[2], 3)

    def test_staff_view_handles_empty_loan_history(self):
        self.client.get("/staff")
        with closing(sqlite3.connect(self.database_path)) as database, database:
            database.execute("DELETE FROM loans")

        response = self.client.get("/staff")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No loans recorded.", response.data)
        self.assertIn(b"Basketball", response.data)

    def test_staff_view_reports_unavailable_database(self):
        self.database_path.mkdir(parents=True)
        with self.assertLogs(app.logger, level="ERROR"):
            response = self.client.get("/staff")
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"Staff records are temporarily unavailable.", response.data)
        self.assertNotIn(b"No loans recorded.", response.data)


if __name__ == "__main__":
    unittest.main()
