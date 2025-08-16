import os
import json
from PIL import Image
import pytesseract

def build_text_index(screenshots_folder_path, status_callback=None):
    """
    Scans screenshots, extracts text, creates thumbnails, and saves to an index file.
    """
    APP_DIR = os.path.join(os.path.expanduser("~"), ".screenscorch")
    THUMBNAIL_DIR = os.path.join(APP_DIR, "thumbnails")
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)
    TEXT_INDEX_FILE = os.path.join(APP_DIR, "screenshot_index.json")

    if status_callback:
        status_callback("Starting OCR indexing and thumbnail generation...")

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
                # 1. Extract Text
                extracted_text = pytesseract.image_to_string(img, lang='eng')
                
                # 2. Create and Save Thumbnail
                thumbnail_filename = f"{os.path.splitext(filename)[0]}.jpeg"
                thumbnail_path = os.path.join(THUMBNAIL_DIR, thumbnail_filename)
                
                # Create a copy to avoid modifying the original image object
                img_copy = img.copy()
                img_copy.thumbnail((256, 256)) # Create a thumbnail max 256x256 pixels
                # Convert to RGB if it's RGBA (PNG) to save as JPEG
                if img_copy.mode in ('RGBA', 'P'):
                    img_copy = img_copy.convert('RGB')
                img_copy.save(thumbnail_path, "jpeg")

                # 3. Store all info in the index
                screenshot_info = {
                    "file_path": file_path,
                    "thumbnail_path": thumbnail_path,
                    "text": extracted_text.strip()
                }
                indexed_data.append(screenshot_info)
        
        with open(TEXT_INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(indexed_data, f, indent=4)
        
        if status_callback:
            status_callback(f"✅ Indexing complete! Processed {total_images} images.")
        return True

    except Exception as e:
        if status_callback:
            status_callback(f"❌ Error during indexing: {e}")
        print(e)
        return False