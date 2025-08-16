import os

# Create a dedicated hidden folder in the user's home directory
APP_DIR = os.path.join(os.path.expanduser("~"), ".screenscorch")
os.makedirs(APP_DIR, exist_ok=True)

# Define paths for our index files
TEXT_INDEX_FILE = os.path.join(APP_DIR, "screenshot_index.json")
SEMANTIC_INDEX_FILE = os.path.join(APP_DIR, "semantic_index.json")

# Model configuration
MODEL_NAME = 'all-MiniLM-L6-v2'