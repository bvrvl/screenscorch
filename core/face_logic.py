import os
import json
import numpy as np

APP_DIR = os.path.join(os.path.expanduser("~"), ".screenscorch")
KNOWN_FACES_FILE = os.path.join(APP_DIR, "known_faces.json")

def load_known_faces():
    """Loads the known faces database from a JSON file."""
    if not os.path.exists(KNOWN_FACES_FILE):
        return {}, [] # Return empty if file doesn't exist
    
    with open(KNOWN_FACES_FILE, 'r') as f:
        known_faces_data = json.load(f)
    
    known_face_names = list(known_faces_data.keys())
    known_face_embeddings = [np.array(enc) for enc in known_faces_data.values()]
    return known_face_names, known_face_embeddings

def save_known_face(name, embedding):
    """Adds a new face and name to the database."""
    if not os.path.exists(KNOWN_FACES_FILE):
        known_faces_data = {}
    else:
        with open(KNOWN_FACES_FILE, 'r') as f:
            known_faces_data = json.load(f)
            
    # For simplicity, we just overwrite if the name exists.
    # A real app might handle this more gracefully.
    known_faces_data[name.lower()] = embedding
    
    with open(KNOWN_FACES_FILE, 'w') as f:
        json.dump(known_faces_data, f, indent=4)