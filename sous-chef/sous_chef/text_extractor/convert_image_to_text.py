"""
Run in terminal with poetry run python convert_image_to_text.py
Needs tesseract application installed.
Custom languages might need to be downloaded.
"""
from pathlib import Path

import pytesseract
from PIL import Image

# better results when language is first identified

lang = "eng"
file_path = Path("/Users/alexanderschulz/test_images/")

print("Processing...")
for index, file_path_to_image in enumerate(sorted(file_path.glob("*.png"))):
    print(file_path_to_image)
    image = Image.open(file_path_to_image)
    string = pytesseract.image_to_string(image, lang=lang)
    output_file = file_path_to_image.with_suffix(".txt")
    with open(output_file, "w") as text_file:
        text_file.write(string)
