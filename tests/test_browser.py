"""Real Chromium journey against Django live server and the private PostgreSQL database."""

from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright


@pytest.mark.browser
@pytest.mark.django_db(transaction=True)
def test_review_journey(live_server, user, org):
    evidence = Path(
        "/Users/dw/code/portfolio-python/python-evidence/invoice-reconciliation-workbench"
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            viewport={"width": 1200, "height": 900}, accept_downloads=True
        )
        page = context.new_page()
        page.goto(live_server.url + "/")
        page.get_by_label("Username").fill("reviewer")
        page.get_by_label("Password").fill("demo-pass")
        page.get_by_role("button", name="Sign in").click()
        for kind, content in [
            ("po", "vendor,po,line,currency,quantity,unit_price\nAcme,P1,1,USD,10,2\n"),
            ("receipt", "vendor,po,line,receipt,quantity\nAcme,P1,1,R1,5\n"),
            (
                "invoice",
                "vendor,invoice,po,line,currency,quantity,unit_price\nAcme,I1,P1,1,USD,8,2.5\n",
            ),
        ]:
            page.get_by_label("Kind").select_option(kind)
            page.get_by_label("CSV file").set_input_files(
                {"name": "synthetic.csv", "mimeType": "text/csv", "buffer": content.encode()}
            )
            page.get_by_role("button", name="Validate & import").click()
        assert page.get_by_text("over_received", exact=True).is_visible()
        assert page.get_by_text("price", exact=True).is_visible()
        stale = context.new_page()
        stale.goto(page.url)
        page.get_by_label("Reviewer resolution").fill(
            "Synthetic vendor agreement accepts price and staged delivery."
        )
        page.get_by_role("button", name="Record resolution").click()
        page.screenshot(path=str(evidence / "workflow-review.jpg"), type="jpeg", quality=70)
        page.screenshot(path=str(evidence / "review-workflow.png"), full_page=True)
        stale.get_by_role("button", name="Approve ledger").click()
        assert stale.get_by_role("heading", name="Review changed").is_visible()
        stale.screenshot(path=str(evidence / "stale-approval.png"), full_page=True)
        stale.get_by_role("link", name="Reload latest review").click()
        stale.get_by_role("button", name="Approve ledger").click()
        assert stale.get_by_text("Approved · frozen", exact=True).is_visible()
        with stale.expect_download() as event:
            stale.get_by_role("link", name="Download approved ledger").click()
        downloaded = event.value.path().read_bytes()
        assert b"20.00" in downloaded
        (evidence / "browser-approved-ledger.csv").write_bytes(downloaded)
        stale.reload()
        assert stale.get_by_text("Approved · frozen", exact=True).is_visible()
        browser.close()
