from playwright.sync_api import sync_playwright
import os
BASE = os.path.dirname(os.path.abspath(__file__))
with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        os.path.join(BASE, ".browser"), headless=True, channel="chrome",
        viewport={"width": 1440, "height": 2000})
    page = ctx.new_page()
    page.goto("https://www.tiktok.com/tiktokstudio/content",
              wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(7000)
    if "/login" in page.url:
        print("NOT LOGGED IN")
    else:
        print("URL:", page.url)
        # dump the visible text of each post row: title / views / privacy
        body = page.inner_text("body")
        # count privacy states
        for word in ["Followers", "Everyone", "Only you", "Friends", "Private"]:
            print("%s count in page:" % word, body.count(word))
        page.screenshot(path=os.path.join(BASE, "tt-content.png"), full_page=False)
        print("screenshot saved")
    ctx.close()
