# Campus Sports Equipment Borrowing System

Software Engineering Assignment 1 prototype. It verifies test cards, displays equipment availability and outstanding loans, and lets verified cards borrow and return equipment. The prototype uses a local SQLite database and allows one outstanding loan per card.

## Requirements

- Python 3 and pip
- Packages listed in `requirements.txt`

## Setup

```bash
git clone https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System.git
cd Campus-Sports-Equipment-Borrowing-System
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run the prototype

```bash
python app.py
```

Open `http://127.0.0.1:5000/` and select **Verify Test Card** after entering an ID. The first visit initializes `instance/campus.db` with demo data. Try `20260001` for a registered card, `20260099` for an unregistered card, and `ABC123` for a format error.

In the demo data, `20260001` starts with no active loan and `20260002` starts with an active basketball loan. After verifying an eligible card, select an available item and click **Borrow Equipment**. A successful loan immediately updates the displayed stock and outstanding loan status.

Select **Return Equipment** while the verified card shows an active loan. A successful return clears the displayed loan, restores one unit to stock, and lets the same card borrow again.

The **Equipment availability** table reads current quantities from SQLite on every page load. New databases start with 5 basketballs, 3 footballs, and 0 badminton rackets. The table shows items with zero stock as **Unavailable**.

Open **Staff view** from the homepage or visit `http://127.0.0.1:5000/staff` to view current inventory and active and returned loans. Borrow and return times are shown in UTC. Select **Refresh staff view** after a borrow or return to see the latest records and quantities.

## Tests

If `pytest` is not installed, run `python -m pip install pytest`. Then execute:

```bash
python -m pytest -v
```

Record the actual output, execution date, environment, number of passed/failed tests, and the tested commit SHA. Do not report a test pass until the command has been run.

## B1 traceability

- Requirement / issue: https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/issues/1
- Merged change: https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/pull/2
- Original feature commit: `53138c6`
- Test files: `tests/test_api.py` and `tests/test_validation.py`

## Submission evidence (complete before marking)

- Final submission commit SHA: **[INSERT FULL SHA]**
- Dated test execution log / CI URL: **[INSERT URL]**
- Independent reviewer and review URL (if recorded): **[INSERT URL]**
- Project backlog: report Section 3.1; publish a GitHub Project or linked issues for the full backlog if required.

## Limitations

The prototype uses synthetic test card IDs and local demo data.

## Attribution

Record third-party libraries, reused code and any permitted AI assistance according to the assessment integrity requirements.
