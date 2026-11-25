import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app import app


class PrototypeAPITestCase(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.database_path = Path(directory.name) / "instance" / "campus.db"
        config = patch.dict(app.config, DATABASE=self.database_path)
        config.start()
        self.addCleanup(config.stop)
        self.client = app.test_client()


class CardAPIIntegrationTests(PrototypeAPITestCase):
    def test_home_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Student Card ID", response.data)

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
    def test_home_page_uses_verification_endpoint(self):
        response = self.client.get("/")
        self.assertIn(b'action="/api/verify-card"', response.data)

    def test_accepts_registered_card_after_normalization(self):
        response = self.client.post("/api/verify-card", json={"card_id": " 20260001 "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "valid": True,
            "card_id": "20260001",
            "message": "Test card verified.",
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
        self.database_path.parent.mkdir()
        with closing(sqlite3.connect(self.database_path)) as database, database:
            database.execute("CREATE TABLE registered_cards (card_id TEXT NOT NULL PRIMARY KEY)")
            database.execute("INSERT INTO registered_cards VALUES (?)", ("02026001",))

        self.assertIn(b"Badminton racket", self.client.get("/").data)
        registered = self.client.post("/api/verify-card", json={"card_id": "02026001"})
        demo_card = self.client.post("/api/verify-card", json={"card_id": "20260001"})
        self.assertEqual(registered.status_code, 200)
        self.assertEqual(demo_card.status_code, 404)


if __name__ == "__main__":
    unittest.main()
