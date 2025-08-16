import os
import json
from PIL import Image
import pytesseract

def build_text_index(screenshots_folder_path, status_callback=None):
    """
    Scans a folder for screenshots, extracts text via OCR, and saves to an index file.
    - screenshots_folder_path: The full path to the user's screenshots.
    - status_callback: A function the GUI can provide to receive progress updates.
    """
    APP_DIR = os.path.join(os.path.expanduser("~"), ".screenscorch")
    os.makedirs(APP_DIR, exist_ok=True)
    TEXT_INDEX_FILE = os.path.join(APP_DIR, "screenshot_index.json")

    if status_callback:
        status_callback("Starting OCR indexing...")

    indexed_data = []
    image_extensions = {'.png', '.jpg', '.jpeg'}

    try:
        files = [f for f in os.listdir(screenshots_folder_path) if os.path.splitext(f)[1].lower() in image_extensions]
        total_images = len(files)
        
        for i, filename in enumerate(files):
            file_path = os.path.join(screenshots_folder_path, filename)
            if status_callback:
                status_callback(f"Processing [{i+1}/{total_images}]: {filename}")
            
            with Image.open(file_path) as img:
                extracted_text = pytesseract.image_to_string(img, lang='eng')
                screenshot_info = {"file_path": file_path, "text": extracted_text.strip()}
                indexed_data.append(screenshot_info)
        
        with open(TEXT_INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(indexed_data, f, indent=4)
        
        if status_callback:
            status_callback(f"✅ Indexing complete! Processed {total_images} images.")
        return True

    except Exception as e:
        if status_callback:
            status_callback(f"❌ Error during indexing: {e}")
        return False