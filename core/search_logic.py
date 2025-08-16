import os
import json
import numpy as np
import torch
from sentence_transformers import SentenceTransformer, util
from thefuzz import fuzz
from .face_logic import load_known_faces 

# --- CONFIGURATION ---
APP_DIR = os.path.join(os.path.expanduser("~"), ".screenscorch")
MASTER_INDEX_FILE = os.path.join(APP_DIR, "master_index.json")
CLIP_MODEL_NAME = 'clip-ViT-B-32'
FUZZY_MATCH_THRESHOLD = 85

# --- GLOBAL CACHE ---
clip_model_cache = None
master_index_cache = None

def load_index_and_model_if_needed():
    """Loads master index and CLIP model into cache."""
    global clip_model_cache, master_index_cache
    if master_index_cache is not None:
        return True
    
    try:
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        clip_model_cache = SentenceTransformer(CLIP_MODEL_NAME, device=device)
        with open(MASTER_INDEX_FILE, 'r', encoding='utf-8') as f:
            master_index_cache = json.load(f)
        return True
    except Exception as e:
        print(f"Error loading master index: {e}")
        return False

def perform_ultimate_search(query, top_k=10):
    """
    Performs a multi-modal search:
    1. Checks if the query is a known person's name for a face search.
    2. If not, performs a tiered Text > Fuzzy > Visual (CLIP) search.
    """
    if not load_index_and_model_if_needed():
        return {"error": "Could not load search index. Please run the indexer first."}

    query_lower = query.lower()
    known_face_names, known_face_embeddings = load_known_faces()

    # --- BRANCH 1: FACE SEARCH ---
    if query_lower in known_face_names:
        face_results = []
        target_embedding = known_face_embeddings[known_face_names.index(query_lower)]
        
        for item in master_index_cache:
            if not item['face_embeddings']:
                continue
            
            unknown_embeddings = np.array(item['face_embeddings'])
            # Compare the target face with all faces found in the screenshot
            matches = np.linalg.norm(unknown_embeddings - target_embedding, axis=1) <= 0.6 # This is the tolerance
            if np.any(matches):
                item_copy = item.copy()
                item_copy['match_type'] = f"Face Match: {query.capitalize()}"
                item_copy['score'] = "High"
                face_results.append(item_copy)
        return face_results

    # --- BRANCH 2: TIERED KEYWORD AND VISUAL SEARCH ---
    final_results = []
    found_paths = set()

    # Tier 1: Exact Keyword
    for item in master_index_cache:
        if query_lower in item['text'].lower():
            item_copy = item.copy()
            item_copy['match_type'], item_copy['score'] = "Exact Keyword", "100%"
            final_results.append(item_copy)
            found_paths.add(item['file_path'])

    # Tier 2: Fuzzy Keyword
    fuzzy_matches = []
    for item in master_index_cache:
        if item['file_path'] not in found_paths and fuzz.partial_ratio(query_lower, item['text'].lower()) >= FUZZY_MATCH_THRESHOLD:
            item_copy = item.copy()
            item_copy['match_type'] = "Fuzzy Keyword"
            item_copy['score'] = f"{fuzz.partial_ratio(query_lower, item['text'].lower())}%"
            fuzzy_matches.append(item_copy)
            found_paths.add(item['file_path'])
    fuzzy_matches.sort(key=lambda x: int(x['score'][:-1]), reverse=True)
    final_results.extend(fuzzy_matches)

    # Tier 3: Visual Search (CLIP)
    remaining_items = [item for item in master_index_cache if item['file_path'] not in found_paths]
    if remaining_items:
        clip_embeddings = torch.tensor([item['clip_embedding'] for item in remaining_items], device=clip_model_cache.device)
        query_embedding = clip_model_cache.encode(query, convert_to_tensor=True)
        
        cosine_scores = util.cos_sim(query_embedding, clip_embeddings)[0]
        top_results = torch.topk(cosine_scores, k=min(top_k, len(remaining_items)))

        for score, idx in zip(top_results[0], top_results[1]):
            match_item = remaining_items[idx.item()]
            match_item['match_type'], match_item['score'] = "Visual Concept", f"{score.item():.2f}"
            final_results.append(match_item)
            
    return final_results