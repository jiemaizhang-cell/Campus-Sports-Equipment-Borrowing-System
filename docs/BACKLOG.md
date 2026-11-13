# Prioritised backlog (Assignment 1)

**Status note:** B1 has an existing tracked issue and merged pull request. B2–B8 are proposed backlog items for future implementation; they are **not** asserted completed. The table is a documented plan, not evidence that these issues were created online.

| ID | Priority | Iteration | Requirement | Acceptance criterion |
| --- | --- | --- | --- | --- |
| B1 | P0 | 1 | Card reader OR on-screen test card input | Format-valid card ID accepted; empty and malformed IDs rejected with clear feedback |
| B2 | P0 | 1 | Identity verification | Known test ID accepted; unknown test ID rejected |
| B3 | P0 | 1 | Equipment availability | Display matches database; zero-stock item cannot be borrowed |
| B4 | P0 | 2 | Outstanding-loan detection | Existing active loan identified; cleared on valid return |
| B5 | P0 | 2 | One-item loan rule | Second, duplicate and concurrent active loans refused |
| B6 | P0 | 2 | Borrow equipment | Loan recorded and available quantity decreased exactly once |
| B7 | P0 | 2 | Return equipment | Return recorded and quantity increased exactly once |
| B8 | P1 | 2 | Staff records / inventory | Records available; failed operations leave state consistent |

## Evidence and ownership

- B1 tracked requirement: https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/issues/1
- B1 PR: https://github.com/jiemaizhang-cell/Campus-Sports-Equipment-Borrowing-System/pull/2
- Planned roles: Xierui Xu (coordination), Jiemai Zhang (UI), Yuteng Li (backend/data), Wentao Xie (QA/integration).
- Assign actual ownership and status to each issue only after team confirmation.

## Iteration completion measures

For each task, store the issue URL, PR URL, reviewer, test command/log, and acceptance outcome. Mark tasks complete only after evidence exists.
