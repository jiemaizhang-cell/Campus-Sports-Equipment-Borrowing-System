"""B1: validation of an on-screen *test* card ID, not identity verification."""
import re

CARD_ID_PATTERN = re.compile(r"[0-9]{8}\Z")


def validate_card_id(value):
    """Return (valid, normalized_id, message).

    A demo card ID is exactly eight ASCII digits; surrounding whitespace is ignored.
    This rule is a prototype convention, not the university card format.
    """
    if not isinstance(value, str):
        return False, None, "Card ID must be text."

    normalized = value.strip()
    if not normalized:
        return False, None, "Card ID is required."
    if not CARD_ID_PATTERN.fullmatch(normalized):
        return False, None, "Card ID must contain exactly 8 digits (0–9)."
    return True, normalized, "Card ID format accepted."
