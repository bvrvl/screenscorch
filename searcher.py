import json
import os
import subprocess
from sentence_transformers import SentenceTransformer, util
import torch

# --- CONFIGURATION ---
# The name of our semantically-enriched index file.
SEMANTIC_INDEX_FILE = "semantic_index.json"
# The same model name we used in the embedder.
MODEL_NAME = 'all-MiniLM-L6-v2'
# How many search results to show at once.
TOP_N_RESULTS = 5

# --- GLOBAL VARIABLES ---
# We'll load the model and data once at the start to be efficient.
model = None
corpus_embeddings = None
corpus_data = None

def load_data_and_model():
    """
    Loads the AI model and the semantic index file into memory.
    This is the most time-consuming part, so we only do it once.
    """
    global model, corpus_embeddings, corpus_data

    # --- 1. Load the AI Model ---
    print("🧠 Loading the semantic model...")
    try:
        model = SentenceTransformer(MODEL_NAME)
    except Exception as e:
        print(f"❌ ERROR: Could not load the model. Have you run 'pip install sentence-transformers torch'? Details: {e}")
        return False
    print("✅ Model loaded.")

    # --- 2. Load the Semantic Index ---
    print("💾 Loading semantic index file...")
    try:
        with open(SEMANTIC_INDEX_FILE, 'r', encoding='utf-8') as f:
            corpus_data = json.load(f)
    except FileNotFoundError:
        print(f"❌ ERROR: Semantic index '{SEMANTIC_INDEX_FILE}' not found.")
        print("Please run 'indexer.py' and then 'embedder.py' first.")
        return False
    
    # --- 3. Prepare Embeddings for Search ---
    # We need to extract just the embedding vectors into a format that's fast for searching.
    # We convert our list of lists into a PyTorch tensor, which is a highly optimized data structure for this kind of math.
    embeddings_list = [item['embedding'] for item in corpus_data]
    corpus_embeddings = torch.tensor(embeddings_list, dtype=torch.float32)
    print("✅ Index is ready to search.")
    return True

def search_semantic(query):
    """Performs semantic search."""
    global model, corpus_embeddings, corpus_data

    print(f"\n🧠 Searching for screenshots conceptually related to: '{query}'")
    
    # 1. Encode the user's query into a vector.
    query_embedding = model.encode(query, convert_to_tensor=True)
    
    # 2. This is the magic! Calculate the cosine similarity between the query and all screenshot embeddings.
    # 'util.cos_sim' is a super-fast function from the library to do this.
    cosine_scores = util.cos_sim(query_embedding, corpus_embeddings)[0]
    
    # 3. Find the top N results based on the scores.
    # We use torch.topk to efficiently get the highest scores and their indices.
    top_results = torch.topk(cosine_scores, k=min(TOP_N_RESULTS, len(corpus_data)))

    # 4. Display the results.
    print(f"🎉 Top {len(top_results[0])} results:")
    results_to_display = []
    for score, idx in zip(top_results[0], top_results[1]):
        # Get the original data for the matching screenshot
        match = corpus_data[idx]
        print(f"  - Score: {score:.4f} | Path: {match['file_path']}")
        # We also show a snippet of the text that was in the screenshot for context.
        text_snippet = ' '.join(match['text'].split())[:100] + '...'
        print(f"    Text: \"{text_snippet}\"")
        results_to_display.append(match['file_path'])
    
    return results_to_display

def search_keyword(query):
    """Performs a simple keyword search."""
    print(f"\n🔎 Searching for screenshots with the exact text: '{query}'")
    results = []
    search_term = query.lower()
    for item in corpus_data:
        if search_term in item['text'].lower():
            results.append(item['file_path'])

    if not results:
        print(f"🤷 No results found for '{query}'")
    else:
        print(f"🎉 Found {len(results)} matching screenshots:")
        for i, path in enumerate(results):
            print(f"  [{i+1}] {path}")
    
    return results


def search_loop():
    """Runs the main interactive search loop."""
    while True:
        print("\n" + "="*50)
        query = input("Enter search query (or 'q' to quit): ").strip()

        if query.lower() == 'q':
            print("Exiting screenscorch. Goodbye!")
            break
        if not query:
            continue

        # --- Perform Semantic Search ---
        results = search_semantic(query)
        
        # --- Option to open a file ---
        if results:
            open_choice = input("Enter a number (1, 2, etc.) to open a file, or press Enter to continue: ").strip()
            try:
                choice_index = int(open_choice) - 1
                if 0 <= choice_index < len(results):
                    file_to_open = results[choice_index]
                    print(f"Opening {file_to_open}...")
                    subprocess.run(['open', file_to_open])
                else:
                    print("Invalid number.")
            except (ValueError, IndexError):
                # User pressed Enter or typed non-numeric input, so we just continue.
                pass

# --- Main execution block ---
if __name__ == "__main__":
    if load_data_and_model():
        search_loop()