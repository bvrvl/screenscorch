import json
import subprocess
from sentence_transformers import SentenceTransformer, util
import torch
import os
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

SEMANTIC_INDEX_FILE = "semantic_index.json"
MODEL_NAME = 'all-MiniLM-L6-v2'
TOP_N_RESULTS = 5

# --- GLOBAL VARIABLES ---
model = None
corpus_embeddings = None
corpus_data = None
device = None # Define the device globally

def load_data_and_model():
    """
    Loads the AI model and the semantic index file into memory, ensuring
    all data is on the correct device (CPU or GPU).
    """
    global model, corpus_embeddings, corpus_data, device

    # Automatically detect the best device. 'mps' is for Apple Silicon GPUs.
    if torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    print(f"✅ Using device: {device}")

    # --- 1. Load the AI Model ---
    print("🧠 Loading the semantic model...")
    try:
        model = SentenceTransformer(MODEL_NAME, device=device) # Tell the model which device to use
    except Exception as e:
        print(f"❌ ERROR: Could not load the model. Details: {e}")
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
    embeddings_list = [item['embedding'] for item in corpus_data]
    # Explicitly move the corpus embeddings to our detected device
    corpus_embeddings = torch.tensor(embeddings_list, dtype=torch.float32).to(device)
    print("✅ Index is ready to search.")
    return True

def search_semantic(query):
    """Performs semantic search."""
    global model, corpus_embeddings, corpus_data

    print(f"\n🧠 Searching for screenshots conceptually related to: '{query}'")
    
    # 1. Encode the user's query. The model will automatically place it on the correct device.
    query_embedding = model.encode(query, convert_to_tensor=True)
    
    # 2. This will now work because both tensors are on the same device.
    cosine_scores = util.cos_sim(query_embedding, corpus_embeddings)[0]
    
    # 3. Find the top N results.
    top_results = torch.topk(cosine_scores, k=min(TOP_N_RESULTS, len(corpus_data)))

    # 4. Display the results.
    print(f"🎉 Top {len(top_results[0])} results:")
    results_to_display = []
    for score, idx in zip(top_results[0], top_results[1]):
        match = corpus_data[idx.item()] # Use .item() to get the index as a plain number
        print(f"  - Score: {score:.4f} | Path: {match['file_path']}")
        text_snippet = ' '.join(match['text'].split())[:100] + '...'
        print(f"    Text: \"{text_snippet}\"")
        results_to_display.append(match['file_path'])
    
    return results_to_display

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

        results = search_semantic(query)
        
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
                pass

# --- Main execution block ---
if __name__ == "__main__":
    if load_data_and_model():
        search_loop()