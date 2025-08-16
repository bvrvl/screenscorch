import os
import json
import hashlib
from PIL import Image
import imagehash
from collections import defaultdict

INDEX_FILE = "screenshot_index.json"

NEAR_DUPE_THRESHOLD = 5 

def load_file_paths(file_path):
    """Loads just the file paths from the screenshot index."""
    print("Loading screenshot list...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [item['file_path'] for item in data]
    except FileNotFoundError:
        print(f"❌ ERROR: Index file not found at '{file_path}'")
        print("Please run the 'indexer.py' script first to create the index.")
        return None

def find_exact_duplicates(file_paths):
    """
    Finds exact duplicate files by comparing their MD5 hashes.
    Returns a list of groups, where each group contains paths to identical files.
    """
    print("\n🔎 Searching for EXACT duplicates...")
    hashes = defaultdict(list)
    for path in file_paths:
        if not os.path.exists(path):
            continue # Skip files that might have been deleted
        
        # Read file in chunks to be memory-efficient
        hasher = hashlib.md5()
        with open(path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        file_hash = hasher.hexdigest()
        hashes[file_hash].append(path)
    
    # Return groups of files that have more than one entry (i.e., are duplicates)
    return [group for group in hashes.values() if len(group) > 1]

def find_near_duplicates(file_paths):
    """
    Finds near-duplicate images using perceptual hashing (pHash).
    Returns a list of groups of visually similar images.
    """
    print("\n🎨 Searching for NEAR duplicates (this may take a while)...")
    hashes = {}
    for path in file_paths:
        if not os.path.exists(path):
            continue
        try:
            with Image.open(path) as img:
                # Create a perceptual hash of the image
                p_hash = imagehash.phash(img)
                hashes[path] = p_hash
        except Exception as e:
            print(f"\n⚠️  Could not process image {path}: {e}")

    # Group images by hash similarity
    groups = []
    matched_files = set()

    for path1, hash1 in hashes.items():
        if path1 in matched_files:
            continue
        
        current_group = [path1]
        for path2, hash2 in hashes.items():
            # Don't compare a file to itself or to files already in a group
            if path1 == path2 or path2 in matched_files:
                continue
            
            # Check the "distance" between two hashes.
            if hash1 - hash2 <= NEAR_DUPE_THRESHOLD:
                current_group.append(path2)
        
        if len(current_group) > 1:
            groups.append(current_group)
            # Add all members of the new group to the matched_files set
            for member in current_group:
                matched_files.add(member)

    return groups

def find_low_information_screenshots(file_paths):
    """
    Finds low-information images, defined as images that are almost entirely one color.
    """
    print("\n📉 Searching for low-information screenshots...")
    low_info_files = []
    for path in file_paths:
        if not os.path.exists(path):
            continue
        try:
            with Image.open(path) as img:
                # For efficiency, resize the image to a small thumbnail for analysis.
                img.thumbnail((100, 100))
                # Get a list of (count, color) tuples.
                colors = img.getcolors(img.size[0] * img.size[1])
                if colors:
                    # Sort colors by count (most frequent first)
                    colors.sort(reverse=True)
                    # If the most common color makes up > 98% of the image, it's low-info.
                    total_pixels = img.size[0] * img.size[1]
                    if (colors[0][0] / total_pixels) > 0.98:
                        low_info_files.append(path)
        except Exception as e:
            print(f"\n⚠️  Could not process image {path}: {e}")
    
    return low_info_files

# --- Main execution block ---
if __name__ == "__main__":
    paths = load_file_paths(INDEX_FILE)

    if paths:
        exact_dupes = find_exact_duplicates(paths)
        near_dupes = find_near_duplicates(paths)
        low_info = find_low_information_screenshots(paths)

        print("\n--- ✅ Cleaning Analysis Complete ---")

        if exact_dupes:
            print(f"\n🔥 Found {len(exact_dupes)} groups of EXACT duplicates:")
            for i, group in enumerate(exact_dupes):
                print(f"\n  Group {i+1}:")
                for path in group:
                    print(f"    - {path}")
        else:
            print("\n🔥 No exact duplicates found.")

        if near_dupes:
            print(f"\n🎨 Found {len(near_dupes)} groups of NEAR duplicates:")
            for i, group in enumerate(near_dupes):
                print(f"\n  Group {i+1}:")
                for path in group:
                    print(f"    - {path}")
        else:
            print("\n🎨 No near-duplicates found.")

        if low_info:
            print(f"\n📉 Found {len(low_info)} low-information screenshots:")
            for path in low_info:
                print(f"    - {path}")
        else:
            print("\n📉 No low-information screenshots found.")
        
        print("\nIMPORTANT: This script only SUGGESTS files. No files have been deleted.")