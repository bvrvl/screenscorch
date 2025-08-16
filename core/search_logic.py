import os
import json
from sentence_transformers import SentenceTransformer, util
import torch

# --- CONFIGURATION ---
APP_DIR = os.path.join(os.path.expanduser("~"), ".screenscorch")
TEXT_INDEX_FILE = os.path.join(APP_DIR, "screenshot_index.json")
SEMANTIC_INDEX_FILE = os.path.join(APP_DIR, "semantic_index.json")
MODEL_NAME = 'all-MiniLM-L6-v2'

# --- GLOBAL MODEL CACHE ---
model_cache = None
corpus_embeddings_cache = None
corpus_data_cache = None

def build_semantic_index(status_callback=None):
    """Generates and saves semantic embeddings for the text index."""
    global model_cache
    if model_cache is None:
        if status_callback: status_callback("Loading AI model (first time may be slow)...")
        model_cache = SentenceTransformer(MODEL_NAME)
    
    try:
        with open(TEXT_INDEX_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        if status_callback: status_callback("❌ Text index not found. Please index first.")
        return False

    # This will now contain the thumbnail path
    items_with_text = [item for item in data if item.get('text')]
    all_texts = [item['text'] for item in items_with_text]
    
    if status_callback: status_callback(f"Generating embeddings for {len(all_texts)} texts...")
    embeddings = model_cache.encode(all_texts, show_progress_bar=False)
    
    semantic_data = []
    for item, embedding in zip(items_with_text, embeddings):
        # Create a new dictionary with all old data plus the new embedding
        new_item = {
            "file_path": item["file_path"],
            "thumbnail_path": item.get("thumbnail_path"),
            "text": item["text"],
            "embedding": embedding.tolist()
        }
        semantic_data.append(new_item)

    with open(SEMANTIC_INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(semantic_data, f, indent=4)
    
    if status_callback: status_callback("✅ Semantic index created successfully!")
    return True

def perform_semantic_search(query, top_k=5):
    """Performs a semantic search and returns a list of result dictionaries."""
    global model_cache, corpus_embeddings_cache, corpus_data_cache
    
    if model_cache is None or corpus_embeddings_cache is None:
        try:
            device = "mps" if torch.backends.mps.is_available() else "cpu"
            model_cache = SentenceTransformer(MODEL_NAME, device=device)
            with open(SEMANTIC_INDEX_FILE, 'r', encoding='utf-8') as f:
                # IMPORTANT: We load the SEMANTIC index, which needs the thumbnail path.
                # Let's assume the embedder will pass it through.
                corpus_data_cache = json.load(f)
            
            embeddings_list = [item['embedding'] for item in corpus_data_cache]
            corpus_embeddings_cache = torch.tensor(embeddings_list, dtype=torch.float32).to(device)
        except FileNotFoundError:
            return {"error": "Semantic index not found. Please create it first."}
        except Exception as e:
            return {"error": str(e)}

    query_embedding = model_cache.encode(query, convert_to_tensor=True)
    cosine_scores = util.cos_sim(query_embedding, corpus_embeddings_cache)[0]
    top_results = torch.topk(cosine_scores, k=min(top_k, len(corpus_data_cache)))
    
    results = []
    for score, idx in zip(top_results[0], top_results[1]):
        match = corpus_data_cache[idx.item()]
        results.append({
            "score": f"{score:.4f}",
            "path": match['file_path'],
            "text": ' '.join(match['text'].split())[:100] + '...',
            "thumbnail_path": match.get('thumbnail_path')
        })
    return results