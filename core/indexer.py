import os
import json
from PIL import Image
import pytesseract
import face_recognition
from sentence_transformers import SentenceTransformer
import time
import hashlib

CLIP_MODEL_NAME = 'clip-ViT-B-32'
clip_model_cache = None

def build_master_index(paths_to_scan, on_complete=None, status_callback=None):
    """
    Scans image files and generates or UPDATES a master index.
    - Can accept a folder path or a list of individual file paths.
    - Skips files that have already been indexed and haven't changed.
    - Removes entries from the index if the source file is deleted.
    """
    global clip_model_cache
    
    APP_DIR = os.path.join(os.path.expanduser("~"), ".screenscorch")
    THUMBNAIL_DIR = os.path.join(APP_DIR, "thumbnails")
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)
    MASTER_INDEX_FILE = os.path.join(APP_DIR, "master_index.json")

    # --- 1. Load Existing Index and Create Cache ---
    master_data = []
    existing_files_cache = {}
    if os.path.exists(MASTER_INDEX_FILE):
        try:
            with open(MASTER_INDEX_FILE, 'r', encoding='utf-8') as f:
                master_data = json.load(f)
            # Create a cache for quick lookups: {path: (mod_time, size)}
            for item in master_data:
                if 'mod_time' in item and 'file_size' in item:
                    existing_files_cache[item['file_path']] = (item['mod_time'], item['file_size'])
            if status_callback: status_callback(f"Loaded {len(master_data)} existing records.")
        except (json.JSONDecodeError, IOError):
            if status_callback: status_callback("⚠️ Could not read existing index. Starting fresh.")
            master_data = []

    if status_callback: status_callback("Loading AI models...")
    
    if clip_model_cache is None:
        clip_model_cache = SentenceTransformer(CLIP_MODEL_NAME)

    if status_callback: status_callback("Gathering files to process...")

    # --- 2. Determine the full list of files to process ---
    image_extensions = {'.png', '.jpg', '.jpeg', '.heic', '.webp'}
    files_to_process = []
    
    # If a single folder path is given
    if isinstance(paths_to_scan, str) and os.path.isdir(paths_to_scan):
        for root, _, files in os.walk(paths_to_scan):
            for filename in files:
                if os.path.splitext(filename)[1].lower() in image_extensions:
                    files_to_process.append(os.path.join(root, filename))
    # If a list of file paths is given
    elif isinstance(paths_to_scan, list):
        files_to_process = paths_to_scan

    if not files_to_process:
        if status_callback: status_callback("🤷 No new image files found to process.")
        if on_complete: on_complete()
        return

    total_images = len(files_to_process)
    if status_callback: status_callback(f"Found {total_images} total images. Comparing with index...")

    # --- 3. Main Processing Loop ---
    newly_indexed_count = 0
    processed_paths = set()

    for i, file_path in enumerate(files_to_process):
        processed_paths.add(file_path)
        try:
            # --- Caching Logic ---
            mod_time = os.path.getmtime(file_path)
            file_size = os.path.getsize(file_path)
            
            if file_path in existing_files_cache:
                cached_mod_time, cached_file_size = existing_files_cache[file_path]
                # If file hasn't changed, skip it
                if mod_time == cached_mod_time and file_size == cached_file_size:
                    continue
                else: # File has changed, remove old entry before re-indexing
                    master_data = [item for item in master_data if item['file_path'] != file_path]
            
            # --- Process New or Changed File ---
            if status_callback:
                status_callback(f"Processing [{i+1}/{total_images}]: {os.path.basename(file_path)}")
            
            pil_image = Image.open(file_path)
            original_width, original_height = pil_image.size

            # Create Thumbnail
            thumbnail_filename = f"{hashlib.md5(file_path.encode()).hexdigest()}.jpeg"
            thumbnail_path = os.path.join(THUMBNAIL_DIR, thumbnail_filename)
            img_copy = pil_image.copy()
            img_copy.thumbnail((250, 250), Image.Resampling.LANCZOS)
            if img_copy.mode in ('RGBA', 'P', 'LA'):
                img_copy = img_copy.convert('RGB')
            img_copy.save(thumbnail_path, "jpeg", quality=92)

            # Extract Data
            extracted_text = pytesseract.image_to_string(pil_image, lang='eng')
            clip_embedding = clip_model_cache.encode(pil_image).tolist()
            np_image = face_recognition.load_image_file(file_path)
            face_locations = face_recognition.face_locations(np_image, model="hog") # Using better model
            face_encodings = face_recognition.face_encodings(np_image, face_locations)
            face_encodings_list = [enc.tolist() for enc in face_encodings]

            screenshot_info = {
                "file_path": file_path,
                "thumbnail_path": thumbnail_path,
                "text": extracted_text.strip(),
                "clip_embedding": clip_embedding,
                "face_embeddings": face_encodings_list,
                "face_locations": face_locations,
                "width": original_width,  
                "height": original_height,
                "mod_time": mod_time, # Store for caching
                "file_size": file_size # Store for caching
            }
            master_data.append(screenshot_info)
            newly_indexed_count += 1

        except Exception as e:
            # Using print for critical errors that should appear in the console
            print(f"\n❌ Error processing {os.path.basename(file_path)}: {e}")

    # --- 4. Prune Deleted Files ---
    if status_callback: status_callback("Cleaning up index...")
    initial_count = len(master_data)
    # Check if files in the original index still exist on disk
    master_data = [item for item in master_data if os.path.exists(item['file_path'])]
    deleted_count = initial_count - len(master_data)

    # --- 5. Save Final Index ---
    try:
        with open(MASTER_INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(master_data, f)
        
        final_message = f"✅ Indexing complete! Indexed {newly_indexed_count} new/changed files. "
        if deleted_count > 0:
            final_message += f"Removed {deleted_count} deleted files. "
        final_message += f"Total: {len(master_data)} items."
        if status_callback: status_callback(final_message)

    except Exception as e:
        error_message = f"❌ Critical error saving master index: {e}"
        if status_callback: status_callback(error_message)
        print(error_message)
    
    # --- 6. Signal Completion ---
    if on_complete:
        on_complete()