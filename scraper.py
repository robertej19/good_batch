from playwright.sync_api import sync_playwright
import re
import os

# Fixed block type order
BLOCK_TYPES = ["price_history", "value_sales", "listed_sales"]

def scrape_brickeconomy_all_blocks(minifig_id):
    url = f"https://www.brickeconomy.com/minifig/{minifig_id}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Use headless=True if you're confident CF will allow it
        page = browser.new_page()
        print(f"🔍 Loading {url}")
        page.goto(url, timeout=60000)
        page.wait_for_timeout(6000)
        html = page.content()
        browser.close()

    os.makedirs("debug_blocks", exist_ok=True)

    print("🔍 Searching for all `data.addRows([ ... ]);` blocks...")
    pattern = r"data\.addRows\(\[(.*?)\]\);"
    blocks = re.findall(pattern, html, re.DOTALL)

    print(f"✅ Found {len(blocks)} JS data blocks\n")

    for i, raw_block in enumerate(blocks):
        block = raw_block.strip()
        block_preview = block[:300].replace('\n', ' ').strip()
        block_type = BLOCK_TYPES[i] if i < len(BLOCK_TYPES) else f"unknown_{i+1}"

        filename = f"debug_blocks/{minifig_id}_{block_type}.txt"
        print(f"📦 Block {i+1} — {block_type.upper()} — {len(block)} chars")
        print(f"🔍 Preview: {block_preview}...\n💾 Saved block to {filename}\n")

        with open(filename, "w", encoding="utf-8") as f:
            f.write(block)

if __name__ == "__main__":
    scrape_brickeconomy_all_blocks("SW0131")
