# ScreenScorch

A powerful tool for intelligent screenshot management and retrieval.

---

## 🚀 Features

*   **Semantic Search:** Find screenshots using natural language queries.
*   **Efficient Indexing:** Quickly index your screenshot library for fast searching.
*   **Customizable Configuration:** Tailor the indexing and searching behavior to your needs.
*   **Pythonic Design:** Built with clean and maintainable Python code.

---

## 🛠️ Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/bvrvl/screenscorch.git
    cd screenscorch
    ```

2.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

---

## 💡 Usage

Here's a basic example of how to use ScreenScorch to index and search your screenshots:

```python
from screenscorch import ScreenScorch

# Initialize ScreenScorch
sc = ScreenScorch()

# Index your screenshots (assuming screenshots are in a 'screenshots/' directory)
sc.index_screenshots('screenshots/')

# Search for a screenshot using a descriptive query
results = sc.search("a screenshot of my code editor with a dark theme")

# Print the paths of the most relevant screenshots
for result in results:
    print(result['path'])
```

For more advanced usage and configuration options, please refer to the project's documentation.

---

## 🤝 Contributing

Contributions are welcome! If you'd like to contribute to ScreenScorch, please follow these guidelines:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Make your changes and ensure they are well-tested.
4.  Submit a pull request.

---

## 📜 License

ScreenScorch is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.