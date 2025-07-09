import os
import pandas as pd
from playwright.sync_api import sync_playwright

CLONES_CSV_FILE = "clones.csv"
MANDALORIANS_CSV_FILE = "mandalorians.csv"
IMG_DIR = os.path.join("assets", "images")
URL_TEMPLATE = "https://img.bricklink.com/ItemImage/MN/0/{}.png"

os.makedirs(IMG_DIR, exist_ok=True)

def download_image_with_playwright(img_url, img_path):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        print(f"Loading {img_url} ...")
        response = page.goto(img_url, timeout=60000)
        page.wait_for_timeout(2000)
        if response and response.status == 200:
            content = response.body()
            with open(img_path, "wb") as f:
                f.write(content)
            print(f"Saved {img_path}")
        else:
            print(f"Failed to download {img_url} (status {response.status if response else 'no response'})")
        browser.close()

def scrape_images_from_csv(csv_file, dataset_name):
    """Scrape images for a specific dataset"""
    if not os.path.exists(csv_file):
        print(f"CSV file {csv_file} not found, skipping {dataset_name}")
        return
    
    print(f"\nProcessing {dataset_name}...")
    df = pd.read_csv(csv_file)
    sw_ids = df["SW ID"].dropna().unique()
    
    for sw_id in sw_ids:
        img_url = URL_TEMPLATE.format(sw_id)
        img_path = os.path.join(IMG_DIR, f"{sw_id}.png")
        if not os.path.exists(img_path):
            download_image_with_playwright(img_url, img_path)
        else:
            print(f"Already have {img_path}")

# Scrape images for both datasets
scrape_images_from_csv(CLONES_CSV_FILE, "Clones")
scrape_images_from_csv(MANDALORIANS_CSV_FILE, "Mandalorians")

print("\nImage scraping complete!") 