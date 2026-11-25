# Campus Sports Equipment Borrowing System

Software Engineering Assignment 1 prototype. B1 provides on-screen test card input and format validation. B2 verifies card IDs against synthetic registrations, B3 shows equipment availability, and B4 shows outstanding equipment loans for verified cards. The prototype uses a local SQLite database.

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

In the demo data, `20260001` has no active loan and `20260002` starts with an active basketball loan. Verify either card to see its current loan status.

The **Equipment availability** table reads current quantities from SQLite on every page load. New databases start with 5 basketballs, 3 footballs, and 0 badminton rackets. The table shows items with zero stock as **Unavailable**.

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

The on-screen test card ID is a demonstration input only. Current evidence does not establish campus-card hardware compatibility, live student-database integration, or completed borrowing/returning transactions.

## Attribution

Record third-party libraries, reused code and any permitted AI assistance according to the assessment integrity requirements.
