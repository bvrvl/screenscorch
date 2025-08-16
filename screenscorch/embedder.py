import json
from sentence_transformers import SentenceTransformer
import sys

INPUT_INDEX_FILE = "screenshot_index.json"
OUTPUT_INDEX_FILE = "semantic_index.json"


MODEL_NAME = 'all-MiniLM-L6-v2'

def generate_embeddings():
    """
    Loads the text from the index, generates a vector embedding for each entry,
    and saves the result to a new file.
    """
    # Load the AI Model
    print(f"🧠 Loading the semantic model '{MODEL_NAME}'...")
    print("This may take a moment and will download the model on the first run.")
    try:
        model = SentenceTransformer(MODEL_NAME)
    except Exception as e:
        print(f"❌ ERROR: Could not load the model. Check your internet connection or library installation. Details: {e}")
        return

    print("✅ Model loaded successfully.")

    # Load the Screenshot Index
    try:
        with open(INPUT_INDEX_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ ERROR: Input file '{INPUT_INDEX_FILE}' not found. Please run 'indexer.py' first.")
        return
    
    # Filter out items with no text, as they can't be embedded.
    items_to_process = [item for item in data if item.get('text')]
    if not items_to_process:
        print("🤷 No text found in the index to process. Exiting.")
        return

    print(f"📄 Found {len(items_to_process)} screenshots with text to process.")

    # Generate Embeddings
    # Process all the texts in one big batch for maximum efficiency.
    all_texts = [item['text'] for item in items_to_process]
    
    print("🚀 Generating embeddings for all texts... (This can take some time)")
    # model.encode() converts our list of text strings into a list of vector embeddings.
    embeddings = model.encode(all_texts, show_progress_bar=True)
    
    # Combine and Save
    for item, embedding in zip(items_to_process, embeddings):
        item['embedding'] = embedding.tolist()

    print(f"\n💾 Saving semantic index to '{OUTPUT_INDEX_FILE}'...")
    try:
        with open(OUTPUT_INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(items_to_process, f, indent=4)
        print("✨ Semantic index created successfully!")
    except Exception as e:
        print(f"❌ Failed to save semantic index: {e}")


# --- Main execution block ---
if __name__ == "__main__":
    generate_embeddings()