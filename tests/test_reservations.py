import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch

from app import app
from database import PICKUP_CODE_ALPHABET, PICKUP_CODE_LENGTH


class ReservationAPITestCase(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.database_path = Path(directory.name) / "instance" / "campus.db"
        config = patch.dict(app.config, DATABASE=self.database_path)
        config.start()
        self.addCleanup(config.stop)
        self.client = app.test_client()
        self.client.get("/")

    def database_state(self):
        with closing(sqlite3.connect(self.database_path)) as database:
            stock = database.execute(
                "SELECT item_id, available_quantity FROM equipment ORDER BY item_id"
            ).fetchall()
            loans = database.execute("SELECT * FROM loans ORDER BY loan_id").fetchall()
            reservations = database.execute(
                "SELECT reservation_id, card_id, item_id, pickup_code, status FROM reservations ORDER BY reservation_id"
            ).fetchall()
        return stock, loans, reservations

    def concurrent_posts(self, path, payloads):
        start = Barrier(len(payloads))

        def attempt(payload):
            client = app.test_client()
            start.wait(timeout=5)
            return client.post(path, json=payload)

        with ThreadPoolExecutor(max_workers=len(payloads)) as workers:
            return list(workers.map(attempt, payloads))

    def test_create_reservation_accepts_5_10_15_20_minutes_and_holds_stock(self):
        for duration in (5, 10, 15, 20):
            with self.subTest(duration=duration):
                resp = self.client.post(
                    "/api/reservations",
                    json={"card_id": "20260001", "item_id": 2, "duration_minutes": duration},
                )
                self.assertEqual(resp.status_code, 201)
                res = resp.get_json()["reservation"]
                self.assertEqual(res["status"], "active")
                self.assertEqual(res["available_quantity"], 2)
                self.assertEqual(len(res["pickup_code"]), PICKUP_CODE_LENGTH)
                self.assertTrue(set(res["pickup_code"]).issubset(set(PICKUP_CODE_ALPHABET)))
                self.assertEqual(
                    datetime.fromisoformat(res["expires_at"]) - datetime.fromisoformat(res["reserved_at"]),
                    timedelta(minutes=duration),
                )

                cancel = self.client.post(
                    "/api/reservations/cancel",
                    json={"card_id": "20260001", "reservation_id": res["reservation_id"]},
                )
                self.assertEqual(cancel.status_code, 200)
                self.assertEqual(cancel.get_json()["reservation"]["available_quantity"], 3)

    def test_rejects_invalid_reservation_durations(self):
        original = self.database_state()
        for bad_duration in (0, 30, -10, "abc", True):
            with self.subTest(duration=bad_duration):
                resp = self.client.post(
                    "/api/reservations",
                    json={"card_id": "20260001", "item_id": 1, "duration_minutes": bad_duration},
                )
                self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.database_state(), original)

    def test_rejects_a_reservation_when_no_units_are_available(self):
        original = self.database_state()
        response = self.client.post(
            "/api/reservations", json={"card_id": "20260001", "item_id": 3}
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["message"], "This item is out of stock.")
        self.assertEqual(self.database_state(), original)

    def test_retry_generates_a_unique_code_after_a_collision(self):
        with patch("database._generate_pickup_code", side_effect=["ABC234", "ABC234", "DEF567"]):
            first = self.client.post("/api/reservations", json={"card_id": "20260001", "item_id": 2})
            self.assertEqual(first.status_code, 201)
            original_code = first.get_json()["reservation"]["pickup_code"]
            cancelled = self.client.post("/api/reservations/cancel", json={"pickup_code": original_code})
            self.assertEqual(cancelled.status_code, 200)

            second = self.client.post("/api/reservations", json={"card_id": "20260001", "item_id": 2})

        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.get_json()["reservation"]["pickup_code"], "DEF567")
        stock, _, reservations = self.database_state()
        self.assertEqual(dict(stock)[2], 2)
        self.assertEqual([(row[3], row[4]) for row in reservations], [
            ("ABC234", "cancelled"),
            ("DEF567", "active"),
        ])

    def test_reservation_status_shows_active_reservation_until_cancelled(self):
        created = self.client.post("/api/reservations", json={"card_id": "20260001", "item_id": 2})
        self.assertEqual(created.status_code, 201)
        reservation = created.get_json()["reservation"]

        status = self.client.post("/api/reservations/status", json={"card_id": " 20260001 "})
        self.assertEqual(status.status_code, 200)
        active = status.get_json()["active_reservation"]
        self.assertEqual(active["reservation_id"], reservation["reservation_id"])
        self.assertEqual(active["pickup_code"], reservation["pickup_code"])
        self.assertEqual(active["expires_at"], reservation["expires_at"])

        cancelled = self.client.post(
            "/api/reservations/cancel",
            json={"card_id": "20260001", "reservation_id": reservation["reservation_id"]},
        )
        self.assertEqual(cancelled.status_code, 200)
        status = self.client.post("/api/reservations/status", json={"card_id": "20260001"})
        self.assertEqual(status.status_code, 200)
        self.assertIsNone(status.get_json()["active_reservation"])

    def test_claim_by_pickup_code_creates_loan_without_double_decrementing_stock(self):
        created = self.client.post(
            "/api/reservations",
            json={"card_id": " 20260001 ", "item_id": 2, "duration_minutes": 10},
        )
        self.assertEqual(created.status_code, 201)
        code = created.get_json()["reservation"]["pickup_code"]

        stock, _, _ = self.database_state()
        self.assertEqual(stock, [(1, 5), (2, 2), (3, 0)])

        claimed = self.client.post(
            "/api/reservations/claim",
            json={"pickup_code": f"  {code.lower()}  "},
        )
        self.assertEqual(claimed.status_code, 201)
        payload = claimed.get_json()
        self.assertEqual(payload["reservation"]["status"], "claimed")
        self.assertEqual(payload["loan"]["item_id"], 2)
        self.assertEqual(payload["loan"]["available_quantity"], 2)

        stock_after, loans_after, _ = self.database_state()
        self.assertEqual(stock_after, [(1, 5), (2, 2), (3, 0)])
        self.assertEqual(len(loans_after), 2)

        # Claimed loan can be returned normally
        ret = self.client.post(
            "/api/return",
            json={"card_id": "20260001", "loan_id": payload["loan"]["loan_id"]},
        )
        self.assertEqual(ret.status_code, 200)
        self.assertEqual(ret.get_json()["loan"]["available_quantity"], 3)

    def test_claim_rejects_invalid_claimed_and_cancelled_codes(self):
        missing = self.client.post("/api/reservations/claim", json={"pickup_code": "ZZZZZZ"})
        self.assertEqual(missing.status_code, 404)

        created = self.client.post("/api/reservations", json={"card_id": "20260001", "item_id": 1})
        code = created.get_json()["reservation"]["pickup_code"]

        self.assertEqual(self.client.post("/api/reservations/claim", json={"pickup_code": code}).status_code, 201)
        reuse = self.client.post("/api/reservations/claim", json={"pickup_code": code})
        self.assertEqual(reuse.status_code, 409)
        self.assertIn("already been used", reuse.get_json()["message"])

        # Return loan, create another reservation, cancel it, then try to claim
        loan_id = self.client.post("/api/verify-card", json={"card_id": "20260001"}).get_json()["active_loan"]["loan_id"]
        self.client.post("/api/return", json={"card_id": "20260001", "loan_id": loan_id})

        res2 = self.client.post("/api/reservations", json={"card_id": "20260001", "item_id": 1}).get_json()["reservation"]
        self.assertEqual(self.client.post("/api/reservations/cancel", json={"pickup_code": res2["pickup_code"]}).status_code, 200)
        claim_cancelled = self.client.post("/api/reservations/claim", json={"pickup_code": res2["pickup_code"]})
        self.assertEqual(claim_cancelled.status_code, 409)
        self.assertIn("cancelled", claim_cancelled.get_json()["message"])

    def test_lazy_expiration_restores_stock_and_rejects_claim(self):
        created = self.client.post("/api/reservations", json={"card_id": "20260001", "item_id": 2})
        res = created.get_json()["reservation"]
        self.assertEqual(self.database_state()[0], [(1, 5), (2, 2), (3, 0)])

        with closing(sqlite3.connect(self.database_path)) as database, database:
            database.execute(
                "UPDATE reservations SET expires_at = datetime('now', '-5 minutes') WHERE reservation_id = ?",
                (res["reservation_id"],),
            )

        # Reading equipment triggers lazy expiration and restores stock
        eq = self.client.get("/api/equipment")
        self.assertEqual(eq.status_code, 200)
        football = next(item for item in eq.get_json()["equipment"] if item["item_id"] == 2)
        self.assertEqual(football["available_quantity"], 3)

        claim = self.client.post("/api/reservations/claim", json={"pickup_code": res["pickup_code"]})
        self.assertEqual(claim.status_code, 409)
        self.assertIn("expired", claim.get_json()["message"])

        status = self.client.post("/api/reservations/status", json={"card_id": "20260001"})
        self.assertEqual(status.status_code, 200)
        self.assertIsNone(status.get_json()["active_reservation"])

    def test_mutual_exclusion_between_loans_and_reservations(self):
        # Card 20260002 has an active demo loan -> cannot reserve
        blocked_res = self.client.post("/api/reservations", json={"card_id": "20260002", "item_id": 2})
        self.assertEqual(blocked_res.status_code, 409)

        # Card 20260001 reserves -> cannot walk-in borrow or reserve a second item
        first = self.client.post("/api/reservations", json={"card_id": "20260001", "item_id": 1})
        self.assertEqual(first.status_code, 201)

        second_res = self.client.post("/api/reservations", json={"card_id": "20260001", "item_id": 2})
        self.assertEqual(second_res.status_code, 409)

        walkin_borrow = self.client.post("/api/borrow", json={"card_id": "20260001", "item_id": 2})
        self.assertEqual(walkin_borrow.status_code, 409)

    def test_concurrent_reservations_for_same_card_commit_only_one(self):
        responses = self.concurrent_posts(
            "/api/reservations",
            [
                {"card_id": "20260001", "item_id": 1, "duration_minutes": 5},
                {"card_id": "20260001", "item_id": 2, "duration_minutes": 10},
            ],
        )
        self.assertEqual(sorted(r.status_code for r in responses), [201, 409])
        _, _, reservations = self.database_state()
        active = [r for r in reservations if r[1] == "20260001" and r[4] == "active"]
        self.assertEqual(len(active), 1)

    def test_two_cards_cannot_reserve_the_same_last_unit(self):
        with closing(sqlite3.connect(self.database_path)) as database, database:
            database.execute("INSERT INTO registered_cards (card_id) VALUES ('20260003')")
            database.execute("UPDATE equipment SET available_quantity = 1 WHERE item_id = 2")
        original_loans = self.database_state()[1]

        cards = ("20260001", "20260003")
        responses = self.concurrent_posts(
            "/api/reservations", [{"card_id": card_id, "item_id": 2} for card_id in cards]
        )

        self.assertEqual(sorted(response.status_code for response in responses), [201, 409])
        winner = cards[0] if responses[0].status_code == 201 else cards[1]
        rejected = next(response for response in responses if response.status_code == 409)
        self.assertEqual(rejected.get_json()["message"], "This item is out of stock.")
        stock, loans, reservations = self.database_state()
        self.assertEqual(dict(stock)[2], 0)
        self.assertEqual(loans, original_loans)
        self.assertEqual([(row[1], row[2], row[4]) for row in reservations], [
            (winner, 2, "active"),
        ])

    def test_concurrent_and_repeated_cancellation_restores_stock_once(self):
        original_stock, original_loans, _ = self.database_state()
        created = self.client.post("/api/reservations", json={"card_id": "20260001", "item_id": 2})
        self.assertEqual(created.status_code, 201)
        reservation = created.get_json()["reservation"]
        code_payload = {"pickup_code": reservation["pickup_code"]}

        responses = self.concurrent_posts("/api/reservations/cancel", [
            code_payload,
            {"card_id": "20260001", "reservation_id": reservation["reservation_id"]},
        ])

        self.assertEqual(sorted(response.status_code for response in responses), [200, 409])
        stock, loans, reservations = self.database_state()
        self.assertEqual(stock, original_stock)
        self.assertEqual(loans, original_loans)
        self.assertEqual([(row[0], row[4]) for row in reservations], [
            (reservation["reservation_id"], "cancelled"),
        ])
        retry = self.client.post("/api/reservations/cancel", json=code_payload)
        self.assertEqual(retry.status_code, 409)
        self.assertEqual(self.database_state(), (stock, loans, reservations))

    def test_staff_dashboard_displays_reservations(self):
        created = self.client.post("/api/reservations", json={"card_id": "20260001", "item_id": 2})
        code = created.get_json()["reservation"]["pickup_code"]
        staff = self.client.get("/staff")
        self.assertEqual(staff.status_code, 200)
        html = staff.get_data(as_text=True)
        self.assertIn(code, html)
        self.assertIn("Due (UTC)", html)
        self.assertIn('id="staff-detail-modal"', html)
        self.assertIn('data-summary-modal="overdue_loans"', html)

    def test_staff_dashboard_counts_only_active_loans_past_the_two_hour_deadline(self):
        with closing(sqlite3.connect(self.database_path)) as database, database:
            database.executemany(
                "INSERT INTO registered_cards (card_id) VALUES (?)",
                [("20260003",), ("20260004",), ("20260005",)],
            )
            database.execute("DELETE FROM loans")
            database.executemany(
                "INSERT INTO loans (loan_id, card_id, item_id, borrowed_at, returned_at) VALUES (?, ?, 1, ?, ?)",
                [
                    (1, "20260001", "2026-01-01 10:00:01", None),
                    (2, "20260003", "2026-01-01 10:00:00", None),
                    (3, "20260004", "2026-01-01 09:59:59", None),
                    (4, "20260005", "2026-01-01 09:59:59", "2026-01-01 11:00:00"),
                ],
            )

        connect = sqlite3.connect

        def connect_at_fixed_time(*args, **kwargs):
            database = connect(*args, **kwargs)
            database.create_function("current_timestamp", 0, lambda: "2026-01-01 12:00:00")
            return database

        with patch("database.sqlite3.connect", side_effect=connect_at_fixed_time):
            staff = self.client.get("/staff")

        self.assertEqual(staff.status_code, 200)
        html = staff.get_data(as_text=True)
        for loan_id, due_at, overdue in (
            (1, "12:00:01", False),
            (2, "12:00:00", False),
            (3, "11:59:59", True),
            (4, "11:59:59", False),
        ):
            with self.subTest(loan_id=loan_id):
                row = html.split(f'<tr id="loan-{loan_id}">', 1)[1].split("</tr>", 1)[0]
                self.assertIn(f'2026-01-01T{due_at}Z', row)
                self.assertEqual('class="cell-overdue"' in row, overdue)
        self.assertRegex(
            html,
            r'data-summary-modal="overdue_loans">\s*<span[^\n]+\n\s*<strong class="metric-value">1</strong>',
        )

    def test_pickup_counter_focuses_on_code_claim_and_returns(self):
        counter_page = self.client.get("/counter")
        self.assertEqual(counter_page.status_code, 200)
        self.assertIn(b'id="counter-claim-form"', counter_page.data)
        self.assertNotIn(b"Active loans (return at counter)", counter_page.data)
        self.assertNotIn(b"Pending pickups", counter_page.data)
        self.assertNotIn(b"Equipment availability", counter_page.data)

        created = self.client.post("/api/reservations", json={"card_id": "20260001", "item_id": 2})
        code = created.get_json()["reservation"]["pickup_code"]

        counter_with_res = self.client.get("/counter")
        self.assertEqual(counter_with_res.status_code, 200)
        self.assertNotIn(code.encode(), counter_with_res.data)

        claimed = self.client.post("/api/reservations/claim", json={"pickup_code": code})
        self.assertEqual(claimed.status_code, 201)

    def test_pickup_counter_reports_unavailable_database(self):
        with patch("app.read_staff_dashboard", side_effect=OSError("disk unavailable")):
            response = self.client.get("/counter")
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"Counter records are temporarily unavailable.", response.data)

    def test_home_redirects_returns_while_staff_view_lists_active_loan_return_action(self):
        home_html = self.client.get("/").get_data(as_text=True)
        self.assertIn("Return this item in person at the sports desk counter", home_html)
        self.assertNotIn('id="return-form"', home_html)
        self.assertNotIn("Go to Pickup Counter", home_html)
        self.assertNotIn("Show at Pickup Counter", home_html)

        staff_html = self.client.get("/staff").get_data(as_text=True)
        self.assertIn("20260002", staff_html)
        self.assertIn("staff-row-return", staff_html)

        self.client.post("/api/return", json={"card_id": "20260002", "loan_id": 1})
        after_return_html = self.client.get("/staff").get_data(as_text=True)
        self.assertNotIn("staff-row-return", after_return_html)


if __name__ == "__main__":
    unittest.main()
