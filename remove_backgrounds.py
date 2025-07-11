import os
from rembg import remove
from PIL import Image

INPUT_DIR = 'assets/images'
OUTPUT_DIR = 'assets/images_bg_removed'
os.makedirs(OUTPUT_DIR, exist_ok=True)

if __name__ == "__main__":
    # Only run on sw0202b.png with alpha matting for better separation
    input_path = "assets/images/SW0202b.png"
    output_path = "assets/images_bg_removed/SW0202b.png"
    from rembg import new_session

    test = True
    if test:
        session = new_session(
            alpha_matting=True,
            alpha_matting_foreground_threshold=200,
            alpha_matting_background_threshold=180,
            alpha_matting_erode_size=1
        )
        with Image.open(input_path) as img:
            img_no_bg = remove(img, session=session)
            img_no_bg.save(output_path)
        print(f"Done! Background-removed image saved to {output_path}")

    else:
        for filename in os.listdir(INPUT_DIR):
            print(f"Processing {filename}")
            if not filename.lower().endswith('.png'):
                continue
            input_path = os.path.join(INPUT_DIR, filename)
            output_path = os.path.join(OUTPUT_DIR, filename)
            with Image.open(input_path) as img:
                img_no_bg = remove(img)
                img_no_bg.save(output_path)
        print(f"Done! Background-removed images saved to {OUTPUT_DIR}") 