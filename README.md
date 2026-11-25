# Campus Sports Equipment Borrowing System

Software Engineering Assignment 1 prototype. It verifies test cards, displays live equipment availability, supports on-site borrowing and returning, and provides timed equipment reservations (10, 15, or 20 minutes) with 6-character pickup codes. The prototype uses a local SQLite database and enforces one active loan or reservation per card.

## Requirements

- Python 3 and pip
- Packages listed in `requirements.txt`

## Setup

```bash
git clone https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System.git
cd Campus-Sports-Equipment-Borrowing-System
python3 -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run the prototype

```bash
python app.py
# Optional port override (e.g. if port 5000 is used by macOS AirPlay Receiver):
PORT=5001 python app.py
```

Open `http://127.0.0.1:5000/` and enter a test card ID (or use the quick demo ID chips) to select **Verify Test Card**. The first visit initializes `instance/campus.db` with demo data. Try `20260001` for a registered card with no loan, `20260002` for a card with an active basketball loan, `20260099` for an unregistered card, and `ABC123` for a format error.

### Borrowing, reserving, and returning

- **Borrow on-site**: After verifying an eligible card, select an available item (or click an available row in the inventory table) and click **Borrow Equipment**. On-site and claimed loans have a 2-hour due window.
- **Reserve for pickup**: Select an available item and a hold duration (**10**, **15**, or **20** minutes), then click **Reserve & Get Code**. One unit is held immediately and a unique 6-character pickup code is generated.
- **Claim with pickup code**: Switch to the **Pickup Code** tab (or use the quick claim bar in **Staff view**), enter the 6-character code, and click **Claim Equipment**. Expired reservations automatically release their held unit back to stock.
- **Cancel reservation**: Verify the card again to view its active reservation and click **Cancel Reservation** to release the held unit immediately.
- **Return equipment**: Verify a card with an active loan and click **Return Equipment** to close the loan and restore stock.

### Staff view

Open **Staff view** from the top navigation or visit `http://127.0.0.1:5000/staff` to see KPI summary metrics, live equipment inventory, reservations (`Active`, `Claimed`, `Cancelled`, `Expired`) with quick claim/cancel actions, and loan history with due/overdue indicators, status filters, and search. Timestamps are shown in UTC.

## Tests

If `pytest` is not installed, run `python -m pip install pytest`. Then execute:

```bash
python -m pytest -v
```

Or generate a timestamped evidence log:

```bash
# macOS/Linux
./run_tests.sh
# Windows PowerShell
powershell -ExecutionPolicy Bypass -File .\run_tests_windows.ps1
```

## Traceability

- B1 requirement / issue: https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/issues/1
- B1 merged PR: https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/pull/2
- Backlog & evidence index: `docs/BACKLOG.md`, `docs/EVIDENCE_INDEX.md`
- Test files: `tests/test_api.py`, `tests/test_validation.py`, `tests/test_reservations.py`

## Limitations

The prototype uses synthetic test card IDs and local demo data. No external campus identity system or notification service is connected.

## Attribution

Record third-party libraries (`Flask`, `pytest`), reused code, and any permitted AI assistance according to the assessment integrity requirements.
