"""
Captures screenshots of each Streamlit screen using the locally installed Google Chrome
(Playwright's own Chromium download is blocked on this network, so we use channel="chrome").

Prerequisite: `streamlit run app.py --server.headless true --server.port 8765` running,
with a demo run already seeded (scripts/seed_demo_run.py).

Run: python scripts/capture_screenshots.py
"""
import os
import time

from playwright.sync_api import sync_playwright

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "screenshots")
URL = "http://localhost:8765"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(URL, wait_until="networkidle")
        page.get_by_role("tab", name="Criteria").wait_for(state="visible", timeout=15000)
        page.wait_for_selector("text=Active Evaluation Criteria", timeout=15000)
        time.sleep(1.5)

        page.screenshot(path=os.path.join(OUT_DIR, "01_criteria.png"), full_page=True)

        page.get_by_role("tab", name="Supplier Input").click()
        time.sleep(1)
        page.screenshot(path=os.path.join(OUT_DIR, "02_supplier_input.png"), full_page=True)

        page.get_by_role("tab", name="Leaderboard").click()
        time.sleep(1.5)
        page.screenshot(path=os.path.join(OUT_DIR, "03_leaderboard.png"), full_page=True)

        page.get_by_role("tab", name="Detailed Scorecard").click()
        time.sleep(1.5)
        page.screenshot(path=os.path.join(OUT_DIR, "04_scorecard.png"), full_page=True)

        page.get_by_role("tab", name="Run Details").click()
        time.sleep(1.5)
        page.screenshot(path=os.path.join(OUT_DIR, "05_run_details.png"), full_page=True)

        browser.close()
    print(f"Screenshots written to {OUT_DIR}")


if __name__ == "__main__":
    main()
