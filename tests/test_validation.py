import unittest
from validation import validate_card_id


class CardValidationTests(unittest.TestCase):
    def test_valid_eight_digit_id(self):
        self.assertEqual(validate_card_id("20260001")[:2], (True, "20260001"))

    def test_empty_input_rejected(self):
        self.assertFalse(validate_card_id("")[0])

    def test_whitespace_only_rejected(self):
        self.assertFalse(validate_card_id("   ")[0])

    def test_malformed_alphanumeric_rejected(self):
        self.assertFalse(validate_card_id("ABC123")[0])

    def test_short_id_rejected(self):
        self.assertFalse(validate_card_id("1234567")[0])

    def test_long_id_rejected(self):
        self.assertFalse(validate_card_id("123456789")[0])

    def test_surrounding_spaces_trimmed(self):
        self.assertEqual(validate_card_id(" 20260001 ")[:2], (True, "20260001"))

    def test_non_ascii_digits_rejected(self):
        self.assertFalse(validate_card_id("２０２６０００１")[0])

    def test_missing_or_non_string_rejected(self):
        self.assertFalse(validate_card_id(None)[0])
        self.assertFalse(validate_card_id(20260001)[0])


if __name__ == "__main__":
    unittest.main()
