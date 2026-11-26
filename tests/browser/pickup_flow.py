"""Browser regression tests. Run explicitly with pytest; see the README."""

import re
import sqlite3
from contextlib import closing
from threading import Thread
from unittest.mock import patch

import pytest
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import app


@pytest.fixture
def campus(tmp_path):
    database_path = tmp_path / "campus.db"
    with patch.dict(app.config, DATABASE=database_path):
        with make_server("127.0.0.1", 0, app) as server:
            worker = Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                yield f"http://127.0.0.1:{server.server_port}", database_path
            finally:
                server.shutdown()
                worker.join(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(timeout=15000)
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def page(browser, campus):
    page = browser.new_page(base_url=campus[0])
    page.set_default_timeout(5000)
    try:
        yield page
    finally:
        page.close()


def reserve_football(page):
    page.goto("/")
    page.get_by_label("Student Card ID").fill("20260001")
    page.get_by_role("button", name="Verify Card").click()

    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_role("heading")).to_have_text("Card 20260001")
    dialog.locator("#equipment-item").select_option(label="Football")
    dialog.get_by_role("button", name="15m").click()
    with page.expect_request(lambda request: request.url.endswith("/api/reservations")) as posted:
        dialog.get_by_role("button", name="Reserve & Get Code").click()
    assert posted.value.post_data_json["duration_minutes"] == 15
    code = dialog.locator("#res-pickup-code")
    expect(code).to_have_text(re.compile(r"^[A-Z2-9]{6}$"))
    pickup_code = code.inner_text()
    dialog.get_by_role("button", name="Done").click()
    expect(page.locator("#equipment-2").get_by_role("cell", name="2", exact=True)).to_be_visible()
    return pickup_code


def test_student_reserves_counter_claims_and_staff_returns(page):
    code = reserve_football(page)
    page.get_by_role("link", name="Pickup Counter").click()
    page.get_by_label("6-Character Pickup Code").fill(code.lower())
    page.get_by_role("button", name="Verify & Hand Out").click()
    expect(page.get_by_role("status")).to_contain_text("Claimed Football for card 20260001")

    page.get_by_role("link", name="Staff view").click()
    reservation = page.locator("#reservations-table tbody tr").filter(has_text=code)
    expect(reservation).to_have_attribute("data-status", "claimed")
    stock = page.locator("#equipment-2")
    expect(stock.get_by_role("cell", name="2", exact=True)).to_be_visible()

    loan = page.locator("#loan-history-table tbody tr").filter(has_text="20260001")
    expect(loan.get_by_role("cell", name="Active", exact=True)).to_be_visible()
    loan.get_by_role("button", name="Return", exact=True).click()
    loan.get_by_role("button", name="Confirm?", exact=True).click()
    expect(loan.get_by_role("cell", name="Returned", exact=True)).to_be_visible()
    expect(stock.get_by_role("cell", name="3", exact=True)).to_be_visible()


def test_staff_cancels_and_filters_reservations(page):
    code = reserve_football(page)
    page.get_by_role("link", name="Staff view").click()
    reservation = page.locator("#reservations-table tbody tr").filter(has_text=code)
    expect(reservation).to_have_attribute("data-status", "active")
    reservation.get_by_role("button", name="Cancel", exact=True).click()
    reservation.get_by_role("button", name="Confirm?", exact=True).click()
    expect(reservation).to_have_attribute("data-status", "cancelled")
    expect(page.locator("#equipment-2").get_by_role("cell", name="3", exact=True)).to_be_visible()

    filters = page.get_by_role("group", name="Filter reservations")
    filters.get_by_role("button", name="Active", exact=True).click()
    expect(reservation).to_be_hidden()
    filters.get_by_role("button", name="Cancelled", exact=True).click()
    expect(reservation).to_be_visible()


def test_home_inventory_search_filter_and_pagination(page, campus):
    page.goto("/")
    with closing(sqlite3.connect(campus[1])) as database, database:
        database.executemany(
            "INSERT INTO equipment (name, available_quantity) VALUES (?, 1)",
            [("Tennis ball",), ("Tennis racket",), ("Volleyball",)],
        )
    page.reload()

    pagination = page.locator("#equipment-pagination")
    rows = page.get_by_role("table", name="Equipment availability").get_by_role("rowgroup").last
    expect(rows.get_by_role("row")).to_have_count(5)
    pagination.get_by_role("button", name="Next").click()
    expect(rows.get_by_role("row")).to_have_count(1)
    expect(pagination.get_by_role("button", name="Next")).to_be_disabled()

    search = page.get_by_role("searchbox", name="Search equipment")
    search.fill("  TENNIS ")
    expect(rows.get_by_role("row")).to_have_count(2)
    expect(rows.get_by_role("rowheader", name="Tennis racket")).to_be_visible()
    expect(pagination.get_by_role("button", name="Prev")).to_be_disabled()

    search.fill("Badminton")
    badminton = rows.get_by_role("rowheader", name="Badminton racket")
    expect(badminton).to_be_visible()
    available = page.get_by_role("button", name="Available only")
    available.click()
    expect(available).to_have_attribute("aria-pressed", "true")
    expect(badminton).to_be_hidden()
    available.click()
    expect(badminton).to_be_visible()
