import os
import json
import hashlib
from PIL import Image
import imagehash
from collections import defaultdict

APP_DIR = os.path.join(os.path.expanduser("~"), ".screenscorch")
TEXT_INDEX_FILE = os.path.join(APP_DIR, "screenshot_index.json")

def find_duplicates(status_callback=None):
    """
    Finds exact and near-duplicate images from the index.
    """
    try:
        with open(TEXT_INDEX_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        file_paths = [item['file_path'] for item in data]
    except FileNotFoundError:
        if status_callback: status_callback("❌ Index file not found. Please index first.")
        return None

    # --- Find Exact Duplicates (fast) ---
    if status_callback: status_callback("Scanning for exact duplicates...")
    exact_hashes = defaultdict(list)
    for path in file_paths:
        if not os.path.exists(path): continue
        hasher = hashlib.md5()
        with open(path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        file_hash = hasher.hexdigest()
        exact_hashes[file_hash].append(path)
    
    exact_dupes = [group for group in exact_hashes.values() if len(group) > 1]

    # --- Find Near Duplicates (slower) ---
    if status_callback: status_callback("Scanning for near-duplicates (this may take time)...")
    near_hashes = {}
    for path in file_paths:
        if not os.path.exists(path): continue
        with Image.open(path) as img:
            p_hash = imagehash.phash(img)
            near_hashes[path] = p_hash

    near_dupes = []
    matched_files = set()
    for path1, hash1 in near_hashes.items():
        if path1 in matched_files: continue
        current_group = [path1]
        for path2, hash2 in near_hashes.items():
            if path1 == path2 or path2 in matched_files: continue
            if hash1 - hash2 <= 5: # Threshold for similarity
                current_group.append(path2)
        
        if len(current_group) > 1:
            near_dupes.append(current_group)
            for member in current_group:
                matched_files.add(member)
    
    if status_callback: status_callback("✅ Duplicate scan complete.")
    return {"exact": exact_dupes, "near": near_dupes}