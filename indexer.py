import os
import json
import sys
from PIL import Image
import pytesseract

# Path to the folder
SCREENSHOTS_FOLDER = "/Users/saurabh/Desktop/temp2025/tempMay282025"

# This is the name of the file where the index will be stored.
INDEX_FILE = "screenshot_index.json"

def index_screenshots(folder_path):
    """
    Scans a folder for image files, extracts text using OCR,
    and returns a list of dictionaries containing the file info and text.
    """
    print("🚀 Starting the indexing process...")
    indexed_data = []
    
    # A set of common image file extensions to look for
    image_extensions = {'.png', '.jpg', '.jpeg', '.tiff', '.bmp'}

    # Get a list of all files in the directory
    try:
        files_in_folder = os.listdir(folder_path)
    except FileNotFoundError:
        print(f"❌ ERROR: The folder '{folder_path}' was not found.")
        print("Please check the SCREENSHOTS_FOLDER path in the script and try again.")
        return None

    image_files = [f for f in files_in_folder if os.path.splitext(f)[1].lower() in image_extensions]
    total_images = len(image_files)
    print(f"✅ Found {total_images} images to process.")

    for i, filename in enumerate(image_files):
        file_path = os.path.join(folder_path, filename)
        
        # Display progress in the terminal on a single line
        progress = f"[{i+1}/{total_images}]"
        sys.stdout.write(f"\r📄 Processing: {progress} {filename[:50]:<50}")
        sys.stdout.flush()

        try:
            # Open the image file using the Pillow library
            with Image.open(file_path) as img:
                # Use Tesseract to perform OCR and extract text
                extracted_text = pytesseract.image_to_string(img)
                
                # Store the information for this screenshot
                screenshot_info = {
                    "file_path": file_path,
                    "text": extracted_text.strip() # .strip() removes leading/trailing whitespace
                }
                indexed_data.append(screenshot_info)

        except Exception as e:
            # If an error occurs (e.g., a corrupted file), print it and continue
            print(f"\n⚠️  Skipping file {filename} due to an error: {e}")

    sys.stdout.write("\n") # Move to the next line after the progress bar is done
    return indexed_data

def save_index(data, file_path):
    """Saves the indexed data to a JSON file."""
    print(f"\n💾 Saving index to {file_path}...")
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        print("✨ Index saved successfully!")
    except Exception as e:
        print(f"❌ Failed to save index: {e}")

# --- Main execution block ---
if __name__ == "__main__":
    
    # Run the main indexing function
    all_data = index_screenshots(SCREENSHOTS_FOLDER)
    
    if all_data:
        save_index(all_data, INDEX_FILE)
    elif all_data is None:
        # This case handles the FileNotFoundError from earlier
        print("Indexing stopped due to configuration error.")
    else:
        print("No images were found to index in the specified folder.")