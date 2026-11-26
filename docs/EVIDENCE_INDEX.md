# Assignment 1 evidence index

Repository: https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System

| Required evidence | Direct link / artifact | Current verification |
| --- | --- | --- |
| Backlog | `docs/BACKLOG.md` | Updated through B1–B11 |
| Tracked requirement (B1) | https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/issues/1 | Existing GitHub Issue #1 |
| Reviewed change (B1) | https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/pull/2 | Merged PR |
| Feature PRs (B4–B8) | PR #12–#16 on `main` | Merged to `main` |
| Reservation, login & system-split PRs (B9–B11) | PR #18–#20 on `main` | Merged to `main` |
| Automated test source | `tests/test_api.py`, `tests/test_validation.py`, `tests/test_reservations.py` | Verified locally with `pytest` (63 tests) |
| CI workflow | `.github/workflows/tests.yml` | Configured for `main`, `feature/**`, and PRs |
| Cross-platform test runners | `run_tests.sh`, `run_tests_windows.ps1` | Saves timestamped logs and JUnit XML to `evidence/` |

## Acceptance trial mapping

- TC1: valid 8-digit ID & password → authenticated session established; cross-card requests rejected (`401`/`403`) and password change updates hash
- TC2: empty/malformed ID or wrong password → rejected with clear feedback and no DB mutation
- TC3: borrow & return → stock decrements/restores atomically; one active loan per card enforced; returns confirmed via Staff view modal
- TC4: reservation & pickup code → 5 min borrow or 5/10/15/20 min hold locks 1 unit, generates 6-char code, claims cleanly at `/counter` into a 2-hour loan, and restores stock on cancel or expiry
