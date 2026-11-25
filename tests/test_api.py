import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app import app


class CardAPIIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

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


class CardVerificationTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.database_path = Path(directory.name) / "instance" / "campus.db"
        config = patch.dict(app.config, DATABASE=self.database_path)
        config.start()
        self.addCleanup(config.stop)
        self.client = app.test_client()

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


if __name__ == "__main__":
    unittest.main()
