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
    Finds exact and near-duplicate images, returning full object info including thumbnail paths.
    """
    try:
        with open(TEXT_INDEX_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Create a fast lookup map from file_path to the full object
        path_to_object_map = {item['file_path']: item for item in data}
        
    except FileNotFoundError:
        if status_callback: status_callback("❌ Index file not found. Please index first.")
        return None

    # --- Find Exact Duplicates ---
    if status_callback: status_callback("Scanning for exact duplicates...")
    exact_hashes = defaultdict(list)
    for path in path_to_object_map.keys():
        if not os.path.exists(path): continue
        hasher = hashlib.md5()
        with open(path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        file_hash = hasher.hexdigest()
        exact_hashes[file_hash].append(path)
    
    exact_dupes_groups = [
        [path_to_object_map[path] for path in group] 
        for group in exact_hashes.values() if len(group) > 1
    ]

    # --- Find Near Duplicates ---
    if status_callback: status_callback("Scanning for near-duplicates (this may take time)...")
    near_hashes = {}
    for path in path_to_object_map.keys():
        if not os.path.exists(path): continue
        with Image.open(path) as img:
            p_hash = imagehash.phash(img)
            near_hashes[path] = p_hash

    near_dupes_groups = []
    matched_files = set()
    for path1, hash1 in near_hashes.items():
        if path1 in matched_files: continue
        current_group_paths = [path1]
        for path2, hash2 in near_hashes.items():
            if path1 == path2 or path2 in matched_files: continue
            if hash1 - hash2 <= 10: # Threshold for similarity
                current_group_paths.append(path2)
        
        if len(current_group_paths) > 1:
            near_dupes_groups.append([path_to_object_map[path] for path in current_group_paths])
            for path in current_group_paths:
                matched_files.add(path)
    
    if status_callback: status_callback("✅ Duplicate scan complete.")
    return {"exact": exact_dupes_groups, "near": near_dupes_groups}