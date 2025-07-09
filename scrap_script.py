import os
import re
import csv
from playwright.sync_api import sync_playwright
import sys

# Constants
BLOCK_TYPES = ["price_history", "value_sales", "listed_sales"]
OUTPUT_CSV = "all_minifig_value_sales.csv"
DEBUG_DIR = "debug_blocks"
MINIFIG_IDS = ["SW0091", "SW0315"]

os.makedirs(DEBUG_DIR, exist_ok=True)

def extract_value_sales_rows(js_data_block):
    """
    Extracts rows from the JS block of the form:
    [new Date(2022, 0, 1), 79.35, 81.00, 85.96, 89.27, 'January 2022   $81.00 - $85.96']
    """
    row_pattern = r"\[new Date\((\d+), (\d+), (\d+)\), ([\d.]+), ([\d.]+), ([\d.]+), ([\d.]+), '([^']+)'\]"
    matches = re.findall(row_pattern, js_data_block)

    rows = []
    for match in matches:
        year, month, day = map(int, match[:3])
        low, q1, q3, high = map(float, match[3:7])
        tooltip = match[7]
        date = f"{year:04d}-{month+1:02d}-01"  # Normalize to YYYY-MM-01
        rows.append((date, low, q1, q3, high, tooltip))
    return rows

def scrape_and_parse_value_sales(minifig_id):
    url = f"https://www.brickeconomy.com/minifig/{minifig_id}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        print(f"🔍 Loading {url}")
        page.goto(url, timeout=60000)
        page.wait_for_timeout(6000)
        html = page.content()
        browser.close()

    # Extract all blocks of form: data.addRows([ ... ]);
    pattern = r"data\.addRows\(\[(.*?)\]\);"
    blocks = re.findall(pattern, html, re.DOTALL)

    if len(blocks) < 2:
        print(f"⚠️ Only found {len(blocks)} blocks for {minifig_id}")
        return []

    value_sales_block = blocks[1]
    filename = f"{DEBUG_DIR}/{minifig_id}_value_sales.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(value_sales_block)

    rows = extract_value_sales_rows(value_sales_block)
    print(f"✅ Parsed {len(rows)} rows for {minifig_id}")
    return [(minifig_id, *row) for row in rows]

def write_combined_csv(all_rows, filename=OUTPUT_CSV):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["SW_ID", "Date", "Low", "Q1", "Q3", "High", "Tooltip"])
        writer.writerows(all_rows)
    print(f"\n💾 Combined CSV saved to {filename}")

if __name__ == "__main__":
    # Accept SW IDs from command line if provided
    if len(sys.argv) > 1:
        minifig_ids = sys.argv[1:]
    else:
        minifig_ids = MINIFIG_IDS

    all_rows = []
    for minifig_id in minifig_ids:
        try:
            rows = scrape_and_parse_value_sales(minifig_id)
            all_rows.extend(rows)
        except Exception as e:
            print(f"❌ Error scraping {minifig_id}: {e}")

    write_combined_csv(all_rows)
