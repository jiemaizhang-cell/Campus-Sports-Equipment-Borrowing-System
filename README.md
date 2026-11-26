# Campus Sports Equipment Borrowing System

Software Engineering Assignment 1 prototype built with Flask and SQLite. It separates student self-service borrowing from front-desk staff operations into two distinct portals, protects student actions with password authentication and server-side sessions (no self-registration), issues 6-character pickup codes for both immediate 5-minute pickup and timed reservations (**5**, **10**, **15**, or **20** minutes), and enforces one active loan or reservation per card.

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
PORT=5050 python app.py
```

The first request initializes `instance/campus.db` with demo data. Student and staff interfaces are separated into two independent systems with no cross-navigation links:

### 1. Student Borrowing Portal (`/login` and `/`)

Open `http://127.0.0.1:5000/login` (or `http://127.0.0.1:5050/login` if overriding port) and sign in with a registered 8-digit student card ID and password. Unauthenticated visits to `/` redirect to `/login`, and self-registration is disabled.

- **Demo accounts**:
  - `20260001` / initial password `0001` (registered, free)
  - `20260002` / initial password `0002` (registered, has an active Basketball loan)
- **Borrow Now (5m pickup)**: After signing in, select an available item (or click an available row in the inventory table) and click **Borrow Now (5m pickup)** to hold 1 unit and receive a 6-character pickup code valid for 5 minutes.
- **Reserve & Get Code**: Select an available item and a hold duration (**5**, **10**, **15**, or **20** minutes), then click **Reserve & Get Code**. One unit is held immediately and a unique 6-character pickup code is generated with a live countdown.
- **Cancel reservation**: Click **Cancel Reservation** (two-step confirmation) on your active ticket to release the held unit immediately. Expired holds automatically release stock back to inventory.
- **Change Password & Log out**: Click **Change Password** in the top bar to update your own password (`6–64` characters, verifying your current password), or click **Log out** to end the session. All student endpoints enforce server-side session checks (`401`/`403`) so no user can act on another student's card.

### 2. Staff Desk System (`/counter` and `/staff`)

- **Pickup Counter** (`http://127.0.0.1:5000/counter`): Minimal handover screen where staff enter the student's 6-character pickup code and click **Verify & Hand Out** to convert the held reservation into an active 2-hour loan without double-decrementing stock.
- **Staff view** (`http://127.0.0.1:5000/staff`): Displays KPI summary metrics and detail modals, live equipment inventory, reservations (`Active`, `Claimed`, `Cancelled`, `Expired`) with quick claim/cancel actions, loan history with due/overdue indicators, status filters, search, a standalone **Refresh staff view** button, and a **Return** confirmation modal to close active loans and restore stock. Timestamps are shown in UTC.

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

The automated suite contains **63 tests** across `tests/test_api.py` (36), `tests/test_reservations.py` (18), and `tests/test_validation.py` (9).

The optional browser tests exercise the reservation, pickup, return, cancellation, and inventory controls in Chromium against a temporary database. With the project virtual environment active, run:

```bash
python -m pip install pytest playwright
python -m playwright install chromium --only-shell
python -m pytest -v tests/browser/pickup_flow.py
```

## Traceability

- B1 requirement / issue: https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/issues/1
- B1 merged PR: https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/pull/2
- Backlog & evidence index: `docs/BACKLOG.md`, `docs/EVIDENCE_INDEX.md`
- Test files: `tests/test_api.py`, `tests/test_validation.py`, `tests/test_reservations.py`

## Limitations

The prototype uses synthetic test card IDs and local demo data. No external campus identity system or notification service is connected.

## Attribution

Record third-party libraries (`Flask`, `Werkzeug`, `pytest`), reused code, and any permitted AI assistance according to the assessment integrity requirements.
