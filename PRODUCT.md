# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Primary users:** Campus students visiting or booking sports equipment at the university sports desk using an 8-digit test student card ID.
- **Secondary users:** Sports desk staff auditing available equipment, checking out reserved items via 6-character pickup codes, and tracking active or overdue loans.

## Product Purpose

Provide a reliable, self-contained prototype for verifying student test cards, displaying real-time equipment availability, borrowing and returning equipment on-site, and reserving available equipment for timed pickup (10, 15, or 20 minutes) with a unique 6-character pickup code.

## Positioning

Combines immediate walk-in borrowing and timed pickup-code reservations in one atomic SQLite-backed workflow, enforcing a strict one-item-per-card rule across both loans and active reservations without external infrastructure.

## Operating Context

- Runs locally via Flask and SQLite (`python app.py`), with zero external runtime or CDN dependencies.
- Demo test cards: `20260001` (registered, initially free), `20260002` (registered, initially has 1 active Basketball loan), `20260099` (unregistered), `ABC123` (invalid format).
- Loans carry a 2-hour due window (`due_at`); expired reservations automatically release held stock back to inventory.

## Capabilities and Constraints

- B1–B8: Card format validation, registration verification, live inventory table, active loan detection, single-item-per-card enforcement, borrow/return transactions, and staff dashboard.
- B9–B11: Timed reservation (10/15/20 minutes) with 6-character unambiguous pickup code, claim-by-code conversion to loan, cancellation, lazy expiration, and staff reservation management.
- Must preserve all existing DOM and API contracts verified by the 52 automated tests in `tests/`.

## Product Principles

1. **One clear focus per state:** Show only the verification step first; once verified, show only the action valid for that card's current state.
2. **Consistency across channels:** Walk-in borrowing and reservation pickup share the same inventory pool, 2-hour loan window, and single-item limit.
3. **Zero external fragility:** Pure server-rendered templates and native CSS/JS that work offline and load instantaneously.
