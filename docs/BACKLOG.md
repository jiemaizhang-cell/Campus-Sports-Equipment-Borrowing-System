# Prioritised backlog (Assignment 1)

| ID | Priority | Iteration | Requirement | Acceptance criterion | Status |
| --- | --- | --- | --- | --- | --- |
| B1 | P0 | 1 | Card reader OR on-screen test card input | Format-valid card ID accepted; empty and malformed IDs rejected with clear feedback | Implemented (`tests/test_validation.py`, `tests/test_api.py`) |
| B2 | P0 | 1 | Identity verification | Known test ID accepted; unknown test ID rejected | Implemented (`tests/test_api.py`) |
| B3 | P0 | 1 | Equipment availability | Display matches database; zero-stock item cannot be borrowed | Implemented (`tests/test_api.py`) |
| B4 | P0 | 2 | Outstanding-loan detection | Existing active loan identified; cleared on valid return | Implemented (`tests/test_api.py`) |
| B5 | P0 | 2 | One-item loan rule | Second, duplicate and concurrent active loans refused | Implemented (`tests/test_api.py`) |
| B6 | P0 | 2 | Borrow equipment | Loan recorded and available quantity decreased exactly once | Implemented (`tests/test_api.py`) |
| B7 | P0 | 2 | Return equipment | Return recorded and quantity increased exactly once | Implemented (`tests/test_api.py`) |
| B8 | P1 | 2 | Staff records / inventory | Records available; failed operations leave state consistent | Implemented (`tests/test_api.py`) |
| B9 | P1 | 3 | Timed borrowing/reservation with pickup code & student auth | Student signs in via card ID + password (self-service password change, no registration); Borrow Now (5m) or Reserve (5/10/15/20 min) holds 1 unit and generates a unique 6-char pickup code; session isolation blocks cross-card actions | Implemented (`tests/test_reservations.py`, `tests/test_api.py`) |
| B10 | P1 | 3 | Minimal counter pickup claim, cancel & lazy expiry | Separate `/counter` claims valid pickup codes into 2-hour loans without double-decrementing stock; student/staff cancel or lazy expiry restores stock automatically | Implemented (`tests/test_reservations.py`) |
| B11 | P1 | 3 | Separated Staff dashboard & return confirmation | Separate `/staff` displays reservations, quick claim/cancel, KPI summary modals, 2-hour loan due/overdue indicators, and modal-confirmed loan returns | Implemented (`tests/test_reservations.py`, `tests/test_api.py`) |

## Evidence and ownership

- B1 tracked requirement: https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/issues/1
- B1 PR: https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/pull/2
- B4–B8 PRs: #12–#16 on `main`
- B9–B11, student login/password & system split PRs: #18–#20 on `main`
- Planned roles: Xierui Xu (coordination), Jiemai Zhang (UI), Yuteng Li (backend/data), Wentao Xie (QA/integration).

## Iteration completion measures

For each task, record the branch/PR, reviewer, test command/log, and acceptance outcome.
