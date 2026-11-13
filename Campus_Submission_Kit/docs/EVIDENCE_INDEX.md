# Assignment 1 evidence index

Repository: https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System

| Required evidence | Direct link / artifact | Current verification |
| --- | --- | --- |
| Backlog | `docs/BACKLOG.md` (publish this file to repository) | Prepared locally; not yet published |
| Tracked requirement | https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/issues/1 | Existing GitHub Issue #1 |
| Reviewed change | https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/pull/2 | Merged PR; independent submitted review not verified |
| Original feature commit | https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/commit/53138c6 | B1 feature commit (short SHA) |
| Automated test source | https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/tree/main/tests | Test files are present; passing run not confirmed |
| CI workflow | `.github/workflows/tests.yml` after publishing | Prepared locally; run not yet completed |
| Test run results | **[ADD URL TO GITHUB ACTIONS RUN OR LOG]** | Pending actual execution |
| Reviewer approval/comments | **[ADD ACTUAL REVIEW URL]** | Pending independent review |
| Submission commit | **[ADD FULL MAIN SHA AFTER ALL UPLOADS]** | Pending final repository state |

## Acceptance trial mapping

- TC1: valid 8-digit ID → format accepted
- TC2: empty ID → rejected with clear feedback
- TC3: malformed ID → rejected with clear feedback
- TC4: repeated invalid submission → consistent rejection and no unexpected state change (only claim automated coverage if test exists)

Record execution date, environment, pass/fail counts, and evidence URL before stating results in the report. Do not mistake expected test outcomes for observed outcomes.
