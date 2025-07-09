from playwright.sync_api import sync_playwright

def test_brickeconomy_page(minifig_id="SW0131"):
    url = f"https://www.brickeconomy.com/minifig/{minifig_id}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)

        page = browser.new_page()
        page.goto(url, timeout=60000)

        # Screenshot to check load
        page.screenshot(path="debug_screenshot.png", full_page=True)

        # Try extracting something simple
        try:
            h1 = page.locator("h1").inner_text()
            print("Minifig Name:", h1)
        except Exception as e:
            print("Failed to read <h1>:", e)

        # Dump HTML to inspect
        html = page.content()
        with open("debug_dump.html", "w", encoding="utf-8") as f:
            f.write(html)

        print("✅ Done")
        browser.close()

if __name__ == "__main__":
    test_brickeconomy_page()
