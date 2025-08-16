import json
import os
import subprocess
import sys

INDEX_FILE = "screenshot_index.json"

def load_index(file_path):
    """Loads the screenshot index from the JSON file."""
    print("Loading search index...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print("✅ Index loaded successfully.")
        return data
    except FileNotFoundError:
        print(f"❌ ERROR: Index file not found at '{file_path}'")
        print("Please run the 'indexer.py' script first to create the index.")
        return None
    except json.JSONDecodeError:
        print(f"❌ ERROR: Could not read the index file. It might be corrupted.")
        return None

def search_loop(index_data):
    """Runs the main interactive search loop."""
    while True:
        # Get input from the user
        query = input("\nEnter a search query (or 'q' to quit): ").strip()

        if query.lower() == 'q':
            print("Exiting screenscorch. Goodbye!")
            break
        
        if not query:
            continue

        results = []
        # Convert the query to lowercase for case-insensitive search
        search_term = query.lower()

        # Loop through every entry in our index
        for item in index_data:
            # Check if the search term is in the extracted text (also lowercase)
            if search_term in item['text'].lower():
                results.append(item['file_path'])
        
        # --- Display the results ---
        if not results:
            print(f"\n🤷 No results found for '{query}'")
        else:
            print(f"\n🎉 Found {len(results)} matching screenshots for '{query}':")
            for i, file_path in enumerate(results):
                print(f"  [{i+1}] {file_path}")
            
            # Add a feature to open the found files
            open_choice = input("Enter a number to open a file, or press Enter to continue: ").strip()
            if open_choice.isdigit() and 1 <= int(open_choice) <= len(results):
                file_to_open = results[int(open_choice) - 1]
                print(f"Opening {file_to_open}...")
                # Use the 'open' command on macOS to open the file with its default app
                subprocess.run(['open', file_to_open])


# --- Main execution block ---
if __name__ == "__main__":
    index = load_index(INDEX_FILE)
    if index:
        search_loop(index)