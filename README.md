# ScreenScorch

![Status](https://img.shields.io/badge/status-beta-green)
![Platform](https://img.shields.io/badge/platform-macOS-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

A smart, local-first desktop app for macOS that creates a searchable, intelligent library of your screenshots. Find any screenshot using natural language, identify duplicates, and clean up your collection—all with complete privacy.

---
### The Problem it Solves

You take hundreds of screenshots, but finding a specific one is a nightmare of endless scrolling. You remember what it was *about*, but not the filename or date. ScreenScorch is your personal screenshot search engine that understands your intent.

### Core Features

- ✅ **AI-Powered Semantic Search**: Search for "that error message about a database" or "a conversation about project deadlines" and find relevant screenshots instantly, even if they don't contain those exact words.
- ✅ **Rich Search Results**: View results with large, clear thumbnails, file names, and snippets of the recognized text.
- ✅ **Powerful Cleaner**: Automatically scans your collection to find and group **exact duplicates** and **visually similar (near-duplicate)** images, making it easy to reclaim disk space.
- ✅ **Interactive File Management**:
    - Open any screenshot directly.
    - Reveal any screenshot in Finder.
    - Safely move unwanted files to the macOS Trash.
- ✅ **100% Local and Private**: Your screenshots and their search index never leave your machine. No cloud, no servers, no data collection, no subscriptions.

### How It Works

ScreenScorch works in two stages, all performed locally on your Mac:

1.  **Indexing**: It scans your screenshots folder, using Optical Character Recognition (OCR) to read the text in each image and generating a small thumbnail for previews.
2.  **Embedding**: A lightweight, on-device AI model analyzes the extracted text and converts its meaning into a numeric representation (a "vector embedding"). When you search, your query is also converted into a vector, and the app finds the screenshots with the most similar vectors.

### Getting Started (Running from Source)

**1. Prerequisites:**
You must have [Homebrew](https://brew.sh/) installed. Then, install Google's Tesseract OCR engine:
```bash
brew install tesseract
```

**2. Clone the Repository:**
```bash
git clone https://github.com/bvrvl/screenscorch.git
cd screenscorch
```
**3. Set Up the Environment:**
```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install all required libraries
pip install -r requirements.txt
```

**4. Run the App:**
```bash
flet run app.py
```

### How to Use the App

1.  **First-Time Setup**: When you first launch the app, use the `...` menu in the top-right to:
    - **Run Indexer**: This performs the initial scan, OCR, and thumbnail generation. You only need to do this once, or whenever you have many new screenshots.
    - **Run Embedder**: This creates the AI search index from the text.
2.  **Search**: Use the main search bar to type your query. Results will appear below. Click any result to open it, or use its `...` menu for more options.
3.  **Clean**: Click the "Cleaner" button in the bottom navigation. The app will automatically scan for duplicates. Review the groups, check the boxes next to the files you want to remove, and click the "Move Selected to Trash" button.

### Technology Stack

- **GUI Framework**: [Flet](https://flet.dev/) (powered by Flutter)
- **AI / ML**: PyTorch, Sentence-Transformers
- **OCR Engine**: Google's Tesseract
- **Image Processing**: Pillow
- **File System**: send2trash

### Roadmap & Future Ideas

- **Visual Search**: Implement CLIP-based image embeddings to allow searching for images based on their visual content (e.g., "a screenshot of a blue button").
- **Tagging System**: Allow users to add custom tags to screenshots for better organization.

### License

This project is licensed under the MIT License. See the `LICENSE` file for details.