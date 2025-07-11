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

def parse_single_price_block(js_data_block):
    """
    Parses a block like:
    [new Date(2008, 3, 28), 18.00, '$18.00', null, null], ...
    Returns list of tuples: (date, low, q1, q3, high, tooltip)
    """
    import re
    row_pattern = r"\[new Date\((\d+), (\d+), (\d+)\), ([\d.]+), '\$([\d.]+)', null, null\]"
    matches = re.findall(row_pattern, js_data_block)
    rows = []
    for match in matches:
        year, month, day = map(int, match[:3])
        price = float(match[3])
        # Calculate values
        low = round(0.9 * price, 2)
        q1 = round(0.8 * price, 2)
        q3 = round(1.1 * price, 2)
        high = round(1.2 * price, 2)
        tooltip = f"${price:.2f} (approximated quartiles)"
        date = f"{year:04d}-{month+1:02d}-{day:02d}"
        rows.append((date, low, q1, q3, high, tooltip))
    return rows

def scrape_and_parse_value_sales(minifig_id):
    import time
    url = f"https://www.brickeconomy.com/minifig/{minifig_id}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        try:
            page = browser.new_page()
            print(f"🔍 Loading {url}")
            page.goto(url, timeout=5000)
            # Poll for up to 30 seconds for the JS data block to appear
            found = False
            html = ""
            for _ in range(30):  # Try for up to 30 seconds
                html = page.evaluate("document.documentElement.outerHTML")
                if "data.addRows([" in html:
                    found = True
                    break
                time.sleep(1)
            if not found:
                print(f"❌ Timed out waiting for JS data block for {minifig_id}")
                with open(f"debug_timeout_{minifig_id}.html", "w", encoding="utf-8") as f:
                    f.write(html)
                return []
        finally:
            browser.close()

    # Extract all blocks of form: data.addRows([ ... ]);
    pattern = r"data\.addRows\(\[(.*?)\]\);"
    blocks = re.findall(pattern, html, re.DOTALL)

    if len(blocks) < 2:
        print(f"⚠️ Only found {len(blocks)} blocks for {minifig_id}")
        if blocks:
            print(f"Block 0 content (truncated to 500 chars):\n{blocks[0][:500]}\n---END BLOCK---")
            # Try to parse as single price block
            rows = parse_single_price_block(blocks[0])
            print(f"✅ Parsed {len(rows)} single-price rows for {minifig_id}")
            return [(minifig_id, *row) for row in rows]
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
    import sys
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    FAILED_FILE = "failed_minifigs.txt"
    # Retry mode: python information_scraper.py --retry-failures
    if len(sys.argv) > 1 and sys.argv[1] == "--retry-failures":
        # Read failed IDs
        if not os.path.exists(FAILED_FILE):
            print(f"No {FAILED_FILE} found. Nothing to retry.")
            sys.exit(0)
        with open(FAILED_FILE, "r", encoding="utf-8") as f:
            failed_ids = [line.strip() for line in f if line.strip()]
        if not failed_ids:
            print(f"No failed IDs in {FAILED_FILE}.")
            sys.exit(0)
        print(f"Retrying {len(failed_ids)} failed minifig IDs...")
        # Read existing CSV rows (if any)
        existing_rows = []
        if os.path.exists(OUTPUT_CSV):
            with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                existing_rows = list(reader)
        else:
            header = ["SW_ID", "Date", "Low", "Q1", "Q3", "High", "Tooltip"]
        still_failed = []
        appended_count = 0
        for minifig_id in failed_ids:
            print(f"Retrying {minifig_id}")
            try:
                rows = scrape_and_parse_value_sales(minifig_id)
                if rows:
                    # Only append rows that are not already in the CSV (avoid duplicates)
                    new_rows = [row for row in rows if list(map(str, row)) not in existing_rows]
                    if new_rows:
                        with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
                            writer = csv.writer(f)
                            # Write header if file was empty
                            if os.stat(OUTPUT_CSV).st_size == 0:
                                writer.writerow(header)
                            writer.writerows(new_rows)
                        appended_count += 1
                        print(f"✅ Success: {minifig_id} appended to {OUTPUT_CSV}")
                    else:
                        print(f"⚠️ {minifig_id} already present in {OUTPUT_CSV}, skipping append.")
                else:
                    still_failed.append(minifig_id)
                    print(f"❌ Still failed: {minifig_id}")
            except Exception as e:
                import traceback
                print(f"❌ Error retrying {minifig_id}: {e}")
                traceback.print_exc()
                still_failed.append(minifig_id)
        # Write updated failed list
        with open(FAILED_FILE, "w", encoding="utf-8") as f:
            for minifig_id in still_failed:
                f.write(f"{minifig_id}\n")
        print(f"Done. {len(still_failed)} failures remain. {appended_count} succeeded and were appended to {OUTPUT_CSV}.")
        sys.exit(0)
    if len(sys.argv) > 1:
        # Batch mode: scrape all IDs passed as arguments
        minifig_ids = sys.argv[1:]
        all_rows = []
        for minifig_id in minifig_ids:
            print(f"Scraping {minifig_id}")
            try:
                rows = scrape_and_parse_value_sales(minifig_id)
                if rows:
                    all_rows.extend(rows)
                else:
                    # No data found, record as failure
                    with open(FAILED_FILE, "a", encoding="utf-8") as fail_f:
                        fail_f.write(f"{minifig_id}\n")
                    print(f"⚠️ No data for {minifig_id}, recorded in {FAILED_FILE}")
            except Exception as e:
                import traceback
                print(f"❌ Error scraping {minifig_id}: {e}")
                traceback.print_exc()
                # Record failure
                with open(FAILED_FILE, "a", encoding="utf-8") as fail_f:
                    fail_f.write(f"{minifig_id}\n")
                print(f"❌ {minifig_id} recorded in {FAILED_FILE}")
        # Write to CSV for inspection
        if all_rows:
            with open("all_minifig_value_sales.csv", "w", newline="", encoding="utf-8") as f:
                import csv
                writer = csv.writer(f)
                writer.writerow(["SW_ID", "Date", "Low", "Q1", "Q3", "High", "Tooltip"])
                writer.writerows(all_rows)
            print("Results written to all_minifig_value_sales.csv")
    else:
        # Test: only scrape for minifig id 'SW0202b'
        minifig_id = "SW0202b"
        print(f"Testing scrape for {minifig_id}")
        try:
            rows = scrape_and_parse_value_sales(minifig_id)
            for row in rows:
                print(row)
            # Write to CSV for inspection
            if rows:
                with open("all_minifig_value_sales.csv", "w", newline="", encoding="utf-8") as f:
                    import csv
                    writer = csv.writer(f)
                    writer.writerow(["SW_ID", "Date", "Low", "Q1", "Q3", "High", "Tooltip"])
                    writer.writerows(rows)
                print("Results written to all_minifig_value_sales.csv")
        except Exception as e:
            import traceback
            print(f"❌ Error scraping {minifig_id}: {e}")
            traceback.print_exc()
