# ScreenScorch 

![Project Status](https://img.shields.io/badge/status-in%20development-orange)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

A local-first, AI-powered desktop application for macOS that lets you find any screenshot in your collection using natural language. Your screenshots, your computer, your data.

---

- **Find by Meaning:** Search for "that funny chat about dogs" or "the error message from the database" and find it instantly.
- **Entirely Local:** Your screenshots and their index never leave your machine. No cloud, no subscriptions, no privacy concerns.
- **Fast & Native:** A simple, clean interface that feels right at home on macOS.


### Current Status

This project is in **active development**, transitioning from a powerful command-line tool to a full desktop application. The core AI-powered semantic search technology is complete and functional. The next phase is to build the graphical user interface (GUI).

### Features

- ✅ **OCR Text Extraction**: Scans all screenshots to read the text within them.
- ✅ **AI-Powered Semantic Search**: The core engine that understands the *meaning* of your search query.
- 🚧 **Graphical User Interface**: In-progress. A simple, intuitive interface for searching and viewing results.
- ⏳ **Duplicate & Clutter Detection**: A planned feature to help you clean up your screenshot folder.
- ⏳ **Visual Search (Content-based)**: A planned feature to search for images based on what they *look like*, not just the text in them.

### Technology Stack

- **Backend**: Python 3
- **AI/ML**: PyTorch, Sentence-Transformers
- **OCR Engine**: Google's Tesseract
- **GUI Framework**: PyQt6 (planned)

### Running the Current Command-Line Version

While the GUI is being built, you can use the powerful CLI version today.

**1. Prerequisites:**
You must have [Homebrew](https://brew.sh/) installed. Then, install Tesseract:
```bash
brew install tesseract
```

**2. Clone the Repository:**
```bash
git clone https://github.com/your-username/screenscorch.git
cd screenscorch
```

**3. Set up the Environment:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
**4. Run the Tool:**
- **Index your files:** `python3 screenscorch/indexer.py`
- **Create embeddings:** `python3 screenscorch/embedder.py`
- **Search your index:** `python3 screenscorch/searcher.py`

### How to Contribute

This is a personal project, but I'm open to collaboration! If you're interested in helping out, especially with UI/UX design or PyQt development, please open an issue to start a discussion.

### License

This project is licensed under the MIT License. See the `LICENSE` file for details.