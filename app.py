import flet as ft
import subprocess
import threading
import os
from core.indexer import build_text_index
from core.search_logic import build_semantic_index, perform_semantic_search

def main(page: ft.Page):
    # --- APP CONFIGURATION ---
    page.title = "ScreenScorch"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.window_width = 800
    page.window_height = 600

    # --- UI CONTROLS ---
    search_field = ft.TextField(
        hint_text="Search for screenshots by meaning...",
        autofocus=True,
        expand=True,
        on_submit=lambda e: handle_search(e.control.value)
    )
    search_button = ft.IconButton(
        icon=ft.icons.SEARCH,
        on_click=lambda e: handle_search(search_field.value)
    )
    results_list = ft.ListView(expand=True, spacing=10)
    status_bar = ft.Text("Welcome to ScreenScorch! Enter a query to begin.", size=12, color=ft.colors.GREY_600)

    # --- CORE FUNCTIONS ---
    def handle_search(query):
        if not query:
            return
        
        status_bar.value = f"Searching for '{query}'..."
        page.update()

        results = perform_semantic_search(query)
        results_list.controls.clear()

        if isinstance(results, dict) and "error" in results:
            status_bar.value = f"❌ Error: {results['error']}"
        elif not results:
            status_bar.value = f"🤷 No results found for '{query}'."
        else:
            for res in results:
                results_list.controls.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.icons.IMAGE),
                        title=ft.Text(res['path'].split('/')[-1]),
                        subtitle=ft.Text(f"Similarity: {res['score']} | Text: {res['text']}"),
                        on_click=lambda e, path=res['path']: subprocess.run(['open', path])
                    )
                )
            status_bar.value = f"✅ Found {len(results)} results."

        page.update()

    def run_indexing_in_thread(e):
        # We run this in a thread to avoid freezing the UI
        # A real app would need a folder picker, but we'll hardcode for now.
        screenshots_folder = os.path.expanduser("~/Desktop")
        
        def update_status(message):
            status_bar.value = message
            page.update()

        threading.Thread(target=build_text_index, args=(screenshots_folder, update_status)).start()

    def run_embedding_in_thread(e):
        # Also run this in a thread
        def update_status(message):
            status_bar.value = message
            page.update()

        threading.Thread(target=build_semantic_index, args=(update_status,)).start()

    # --- LAYOUT THE PAGE ---
    page.appbar = ft.AppBar(
        leading=ft.Icon(ft.icons.CAMERA_ALT_OUTLINED),
        title=ft.Text("ScreenScorch"),
        actions=[
            ft.PopupMenuButton(items=[
                ft.PopupMenuItem(text="Step 1: Run Indexer", on_click=run_indexing_in_thread),
                ft.PopupMenuItem(text="Step 2: Run Embedder", on_click=run_embedding_in_thread),
            ])
        ]
    )
    page.add(
        ft.Row([search_field, search_button]),
        results_list,
        status_bar
    )

# --- RUN THE APP ---
ft.app(target=main)