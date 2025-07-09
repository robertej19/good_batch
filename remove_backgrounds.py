import os
from rembg import remove
from PIL import Image

INPUT_DIR = 'assets/images'
OUTPUT_DIR = 'assets/images_bg_removed'
os.makedirs(OUTPUT_DIR, exist_ok=True)

for filename in os.listdir(INPUT_DIR):
    if not filename.lower().endswith('.png'):
        continue
    input_path = os.path.join(INPUT_DIR, filename)
    output_path = os.path.join(OUTPUT_DIR, filename)
    with Image.open(input_path) as img:
        img_no_bg = remove(img)
        img_no_bg.save(output_path)
print(f"Done! Background-removed images saved to {OUTPUT_DIR}") 