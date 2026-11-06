import unittest
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


if __name__ == "__main__":
    unittest.main()
