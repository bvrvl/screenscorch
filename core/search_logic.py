import os
import json
from sentence_transformers import SentenceTransformer, util
import torch
from thefuzz import fuzz 

# --- CONFIGURATION ---
APP_DIR = os.path.join(os.path.expanduser("~"), ".screenscorch")
SEMANTIC_INDEX_FILE = os.path.join(APP_DIR, "semantic_index.json")
MODEL_NAME = 'all-MiniLM-L6-v2'
FUZZY_MATCH_THRESHOLD = 85 # A score out of 100 for how similar a typo must be

# --- GLOBAL MODEL CACHE ---
model_cache = None
corpus_embeddings_cache = None
corpus_data_cache = None

def load_index_and_model_if_needed():
    """Loads data into the global cache if it's not already there."""
    global model_cache, corpus_embeddings_cache, corpus_data_cache
    if model_cache is not None and corpus_embeddings_cache is not None:
        return True # Already loaded
    
    try:
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        model_cache = SentenceTransformer(MODEL_NAME, device=device)
        with open(SEMANTIC_INDEX_FILE, 'r', encoding='utf-8') as f:
            corpus_data_cache = json.load(f)
        
        embeddings_list = [item['embedding'] for item in corpus_data_cache]
        corpus_embeddings_cache = torch.tensor(embeddings_list, dtype=torch.float32).to(device)
        return True
    except Exception as e:
        print(f"Error loading index: {e}")
        return False

def perform_unified_search(query, top_k=5):
    """
    Performs a tiered search: Exact > Fuzzy > Semantic.
    """
    if not load_index_and_model_if_needed():
        return {"error": "Could not load the search index. Please run the indexer/embedder."}

    query_lower = query.lower()
    final_results = []
    found_paths = set()

    # --- TIER 1: EXACT KEYWORD MATCH ---
    for item in corpus_data_cache:
        if query_lower in item['text'].lower():
            item_copy = item.copy()
            item_copy['match_type'] = "Exact Keyword"
            item_copy['score'] = "100%"
            final_results.append(item_copy)
            found_paths.add(item['file_path'])

    # --- TIER 2: FUZZY KEYWORD MATCH ---
    fuzzy_matches = []
    for item in corpus_data_cache:
        if item['file_path'] not in found_paths:
            score = fuzz.partial_ratio(query_lower, item['text'].lower())
            if score >= FUZZY_MATCH_THRESHOLD:
                item_copy = item.copy()
                item_copy['match_type'] = "Fuzzy Keyword"
                item_copy['score'] = f"{score}%"
                fuzzy_matches.append(item_copy)
                found_paths.add(item['file_path'])
    
    # Sort fuzzy matches by their score, highest first
    fuzzy_matches.sort(key=lambda x: int(x['score'][:-1]), reverse=True)
    final_results.extend(fuzzy_matches)

    # --- TIER 3: SEMANTIC MATCH ---
    # Prepare the remaining items for semantic search
    remaining_items = []
    remaining_indices = []
    for i, item in enumerate(corpus_data_cache):
        if item['file_path'] not in found_paths:
            remaining_items.append(item)
            remaining_indices.append(i)
    
    if remaining_items:
        remaining_embeddings = corpus_embeddings_cache[remaining_indices]
        query_embedding = model_cache.encode(query, convert_to_tensor=True)
        
        cosine_scores = util.cos_sim(query_embedding, remaining_embeddings)[0]
        top_results_indices = torch.topk(cosine_scores, k=min(top_k, len(remaining_items)))

        for score, idx in zip(top_results_indices[0], top_results_indices[1]):
            match_item = remaining_items[idx.item()]
            match_item['match_type'] = "Semantic"
            match_item['score'] = f"{score.item():.2f}"
            final_results.append(match_item)

    return final_results

# We keep the old embedder function as is
def build_semantic_index(status_callback=None):
    global model_cache
    try:
        with open(os.path.join(APP_DIR, "screenshot_index.json"), 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        if status_callback: status_callback("❌ Text index not found.")
        return False

    if model_cache is None:
        model_cache = SentenceTransformer(MODEL_NAME)
    
    items_with_text = [item for item in data if item.get('text')]
    all_texts = [item['text'] for item in items_with_text]
    
    if status_callback: status_callback(f"Generating embeddings for {len(all_texts)} texts...")
    embeddings = model_cache.encode(all_texts, show_progress_bar=False)
    
    semantic_data = []
    for item, embedding in zip(items_with_text, embeddings):
        item['embedding'] = embedding.tolist()
        semantic_data.append(item)

    with open(SEMANTIC_INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(semantic_data, f, indent=4)
    
    if status_callback: status_callback("✅ Semantic index created successfully!")
    return True