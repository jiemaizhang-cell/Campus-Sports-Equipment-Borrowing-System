# Campus Sports Equipment Borrowing System

A Flask and SQLite prototype for the Software Engineering coursework. Students verify a test card, check available equipment, and borrow or return an item. The staff view shows current stock and loan history.

## Quick start

Use Git and Python 3 with `pip` and `venv` available. The project has been tested with Python 3.12.

```sh
git clone https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System.git
cd Campus-Sports-Equipment-Borrowing-System
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

If `python` opens the Microsoft Store, use the full path to your installed `python.exe` for the virtual environment command.

### macOS or Linux

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

Open the [student page](http://127.0.0.1:5000/) while Flask is running. Select **Staff view** from the homepage or open [the staff page](http://127.0.0.1:5000/staff) directly. Press **Ctrl+C** in the server terminal to stop Flask.

## Demo workflow

On a fresh database, the available stock is five basketballs, three footballs, and zero badminton rackets. The homepage marks zero-stock items as **Unavailable**.

| Test card input | Expected result on a fresh database |
| --- | --- |
| `20260001` | Registered card with no active loan |
| `20260002` | Registered card with an active basketball loan |
| `20260099` | Valid format with no registration |
| `ABC123` | Format error |

1. Enter `20260001` and choose **Verify Test Card**.
2. Select **Football** and click **Borrow Equipment**. On a fresh database, the football stock drops from three to two, and the student page shows an active loan.
3. Open **Staff view** to see the active record. Click **Return Equipment** on the student page to restore the stock and clear the active loan.
4. Select **Refresh staff view** to see the record marked **Returned**, along with the borrow time, return time, and restored stock. The staff page shows times in UTC.

Each card can have one active loan. Borrowing and returning update the loan record and stock in a single SQLite transaction so they stay consistent if a write fails.

## Run tests

Run the suite from the repository root in a separate terminal. The tests use Python's built-in `unittest`, Flask's test client, and temporary SQLite databases.

**Windows PowerShell**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

**macOS or Linux**

```sh
.venv/bin/python -m unittest discover -s tests -v
```

The suite covers card validation, stock display, borrowing, returning, concurrent requests, transaction rollback, and staff records. For a focused concurrency check, add `-k test_concurrent_http_requests_for_one_card_commit_one_loan` to the test command. That case checks that two simultaneous requests for one card leave one active loan and deduct stock once.

## Local data and project files

The first page load creates `instance/campus.db` with synthetic card registrations, equipment, and a sample loan. The database is ignored by Git and persists between runs. For demos, the app uses test card IDs and a read-only staff view.

| Path | Purpose |
| --- | --- |
| [`app.py`](app.py) | Flask entry point and routes |
| [`database.py`](database.py) | SQLite schema, demo data, and loan transactions |
| [`validation.py`](validation.py) | Test card ID format rules |
| [`templates/`](templates/) and [`static/`](static/) | Student and staff pages, styling, and browser interactions |
| [`tests/`](tests/) | Unit and integration tests |

## Requirements and pull requests

| Feature | Issue | Pull request |
| --- | --- | --- |
| B1 Card input and format validation | [#1](https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/issues/1) | [#2](https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/pull/2) |
| B2 Registered card verification | [#3](https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/issues/3) | [#10](https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/pull/10) |
| B3 Equipment availability | [#4](https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/issues/4) | [#11](https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/pull/11) |
| B4 Active loan detection | [#5](https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/issues/5) | [#12](https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/pull/12) |
| B5 One active loan per card | [#6](https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/issues/6) | [#13](https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/pull/13) |
| B6 Borrow equipment | [#7](https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/issues/7) | [#14](https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/pull/14) |
| B7 Return equipment | [#8](https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/issues/8) | [#15](https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/pull/15) |
| B8 Staff inventory and loan history | [#9](https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/issues/9) | [#16](https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/pull/16) |

See the [original backlog](docs/BACKLOG.md) and [Assignment 1 evidence index](docs/EVIDENCE_INDEX.md) for planning and workflow records. For assessment, use the fixed commit or release listed in the submission.

## Attribution

The application uses Flask and Python's standard library. Codex assisted with implementation, tests, and documentation during development.
