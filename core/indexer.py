import os
import json
from PIL import Image
import pytesseract
import face_recognition
from sentence_transformers import SentenceTransformer

CLIP_MODEL_NAME = 'clip-ViT-B-32'
clip_model_cache = None

def build_master_index(screenshots_folder_path, status_callback=None):
    """
    Scans screenshots and generates a master index with OCR text, 
    a CLIP image embedding, all face embeddings, AND original dimensions.
    """
    global clip_model_cache
    
    APP_DIR = os.path.join(os.path.expanduser("~"), ".screenscorch")
    THUMBNAIL_DIR = os.path.join(APP_DIR, "thumbnails")
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)
    MASTER_INDEX_FILE = os.path.join(APP_DIR, "master_index.json")

    if status_callback: status_callback("Loading AI models...")
    
    if clip_model_cache is None:
        clip_model_cache = SentenceTransformer(CLIP_MODEL_NAME)

    if status_callback: status_callback("Starting master indexing process...")

    master_data = []
    image_extensions = {'.png', '.jpg', '.jpeg'}

    try:
        files = [f for f in os.listdir(screenshots_folder_path) if os.path.splitext(f)[1].lower() in image_extensions]
        total_images = len(files)
        
        for i, filename in enumerate(files):
            file_path = os.path.join(screenshots_folder_path, filename)
            if status_callback:
                status_callback(f"Processing [{i+1}/{total_images}]: {filename}")
            
            try:
                pil_image = Image.open(file_path)
                original_width, original_height = pil_image.size

                # --- Create Thumbnail ---
                thumbnail_filename = f"{os.path.splitext(filename)[0]}.jpeg"
                thumbnail_path = os.path.join(THUMBNAIL_DIR, thumbnail_filename)
                img_copy = pil_image.copy()
                img_copy.thumbnail((256, 256))
                if img_copy.mode in ('RGBA', 'P'):
                    img_copy = img_copy.convert('RGB')
                img_copy.save(thumbnail_path, "jpeg")

                # --- Extract Text, Embeddings, Faces (as before) ---
                extracted_text = pytesseract.image_to_string(pil_image, lang='eng')
                clip_embedding = clip_model_cache.encode(pil_image).tolist()
                np_image = face_recognition.load_image_file(file_path)
                face_locations = face_recognition.face_locations(np_image)
                face_encodings = face_recognition.face_encodings(np_image, face_locations)
                face_encodings_list = [enc.tolist() for enc in face_encodings]

                # --- Store all data, including new dimensions ---
                screenshot_info = {
                    "file_path": file_path,
                    "thumbnail_path": thumbnail_path,
                    "text": extracted_text.strip(),
                    "clip_embedding": clip_embedding,
                    "face_embeddings": face_encodings_list,
                    "face_locations": face_locations,
                    "width": original_width,  
                    "height": original_height 
                }
                master_data.append(screenshot_info)

            except Exception as e:
                print(f"\nError processing {filename}: {e}")

        with open(MASTER_INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(master_data, f)
        
        if status_callback:
            status_callback(f"✅ Master index complete! Processed {total_images} images.")
        return True

    except Exception as e:
        if status_callback: status_callback(f"❌ Critical error during indexing: {e}")
        print(e)
        return False