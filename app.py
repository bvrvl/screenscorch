import os
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

import flet as ft
import subprocess
import threading
from send2trash import send2trash
from core.indexer import build_text_index
from core.search_logic import build_semantic_index, perform_semantic_search
from core.cleaner_logic import find_duplicates

def main(page: ft.Page):
    # --- APP CONFIGURATION ---
    page.title = "ScreenScorch"
    page.window_width = 800
    page.window_height = 700
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0

    cleaner_checkboxes = []

    def open_file_in_finder(e, path):
        if os.path.exists(path):
            subprocess.run(["open", "-R", path])

    def move_to_trash(e, path):
        if os.path.exists(path):
            try:
                send2trash(path)
                status_bar.value = f"🗑️ Moved to Trash: {os.path.basename(path)}"
                # A full refresh is the easiest way to update the UI
                run_cleaner_scan() 
            except Exception as ex:
                status_bar.value = f"❌ Error moving to Trash: {ex}"
            page.update()

    # --- UI CONTROLS ---
    search_field = ft.TextField(hint_text="Search your screenshots...", expand=True, on_submit=lambda e: handle_search())
    search_button = ft.IconButton(icon="search", on_click=lambda e: handle_search())
    results_list = ft.ListView(expand=True, spacing=10, item_extent=80)
    search_view = ft.Column(controls=[ft.Row([search_field, search_button]), results_list], visible=True, expand=True)
    
    cleaner_results_view = ft.ListView(expand=True, spacing=15)
    
    def delete_selected_files(e):
        files_to_delete = [cb.data for cb in cleaner_checkboxes if cb.value]
        if not files_to_delete:
            status_bar.value = "No files selected to delete."
            page.update()
            return

        for path in files_to_delete:
            move_to_trash(e, path) # Reuse our single-file delete logic
        
        status_bar.value = f"✅ Moved {len(files_to_delete)} files to Trash."
        page.update()

    delete_selected_button = ft.ElevatedButton(
        text="Move Selected to Trash", icon="delete_sweep", color="white", bgcolor="red600",
        on_click=delete_selected_files, height=40
    )

    cleaner_view = ft.Column(controls=[
        ft.Text("Duplicate & Near-Duplicate Files", size=20, weight=ft.FontWeight.BOLD),
        ft.Text("Review the groups below. Check the files you want to delete.", color="grey_500"),
        ft.Divider(),
        cleaner_results_view,
        ft.Container(content=delete_selected_button, alignment=ft.alignment.center)
    ], visible=False, expand=True)

    status_bar = ft.Text("Welcome!", size=12)

    # --- CORE LOGIC ---
    def handle_search():
        query = search_field.value
        if not query: return
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
                list_item = ft.ListTile(
                    data=res['path'],
                    leading=ft.Image(src=res.get('thumbnail_path'), width=60, height=60, fit=ft.ImageFit.CONTAIN, border_radius=ft.border_radius.all(6)),
                    title=ft.Text(os.path.basename(res['path']), size=14),
                    subtitle=ft.Text(f"Similarity: {res['score']} | {res['text']}", size=12, max_lines=2),
                    on_click=lambda e, p=res['path']: subprocess.run(['open', p])
                )
                list_item.trailing = ft.PopupMenuButton(items=[
                    ft.PopupMenuItem(text="Show in Finder", icon="folder_open", on_click=lambda e, p=res['path']: open_file_in_finder(e, p)),
                    ft.PopupMenuItem(text="Move to Trash", icon="delete", on_click=lambda e, p=res['path']: move_to_trash(e, p)),
                ])
                results_list.controls.append(list_item)
            status_bar.value = f"✅ Found {len(results)} results."
        page.update()

    def run_task_in_thread(target_func, *args):
        def update_status_callback(message):
            status_bar.value = message
            page.update()
        thread = threading.Thread(target=target_func, args=(*args, update_status_callback))
        thread.start()

    def handle_view_change(e):
        selected_index = e.control.data
        search_view.visible = (selected_index == 0)
        search_nav_button.style.bgcolor = "white10" if selected_index == 0 else None
        cleaner_view.visible = (selected_index == 1)
        cleaner_nav_button.style.bgcolor = "white10" if selected_index == 1 else None
        if selected_index == 1:
            run_cleaner_scan()
        page.update()
    
    def run_cleaner_scan():
        nonlocal cleaner_checkboxes
        cleaner_checkboxes.clear()
        status_bar.value = "Starting duplicate scan..."
        cleaner_results_view.controls.clear()
        page.update()
        
        def on_scan_complete(dupes):
            if dupes is None: return
            if not dupes["exact"] and not dupes["near"]:
                cleaner_results_view.controls.append(ft.Text("No duplicates found!", italic=True, text_align=ft.TextAlign.CENTER))
            
            def create_file_row(file_obj, is_checked):
                # We use 'file_path' and 'thumbnail_path' to match the indexer's data structure
                cb = ft.Checkbox(value=is_checked, data=file_obj['file_path'])
                cleaner_checkboxes.append(cb)
                return ft.Row(
                    controls=[
                        cb,
                        ft.Image(src=file_obj['thumbnail_path'], width=50, height=50, fit=ft.ImageFit.CONTAIN, border_radius=ft.border_radius.all(4)),
                        ft.Text(os.path.basename(file_obj['file_path']), expand=True, size=12),
                        ft.IconButton(icon="folder_open", on_click=lambda e, p=file_obj['file_path']: open_file_in_finder(e, p), tooltip="Show in Finder"),
                        ft.IconButton(icon="open_in_new", on_click=lambda e, p=file_obj['file_path']: subprocess.run(['open', p]), tooltip="Open File"),
                    ],
                    alignment=ft.MainAxisAlignment.START
                )

            if dupes["exact"]:
                cleaner_results_view.controls.append(ft.Text("Exact Duplicates", weight=ft.FontWeight.BOLD))
                for group in dupes["exact"]:
                    group_col = ft.Column([create_file_row(file, i > 0) for i, file in enumerate(group)])
                    cleaner_results_view.controls.append(ft.Card(content=ft.Container(group_col, padding=10)))

            if dupes["near"]:
                cleaner_results_view.controls.append(ft.Container(ft.Text("Near Duplicates", weight=ft.FontWeight.BOLD), margin=ft.margin.only(top=20)))
                for group in dupes["near"]:
                    group_col = ft.Column([create_file_row(file, i > 0) for i, file in enumerate(group)])
                    cleaner_results_view.controls.append(ft.Card(content=ft.Container(group_col, padding=10)))
            page.update()

        def scanner_thread_target():
            update_callback = lambda msg: page.run_thread_safe(lambda: setattr(status_bar, 'value', msg) or page.update())
            duplicate_data = find_duplicates(update_callback)
            page.run_thread_safe(on_scan_complete, duplicate_data)
        
        def final_scanner_thread_target():
            def update_status_callback(message):
                status_bar.value = message
                page.update()
            
            duplicate_data = find_duplicates(update_status_callback)
            on_scan_complete(duplicate_data)
        
        threading.Thread(target=final_scanner_thread_target).start()
    
    # --- FINAL PAGE LAYOUT ---
    search_nav_button = ft.TextButton(text="Search", icon="search", data=0, on_click=handle_view_change, style=ft.ButtonStyle(bgcolor="white10"))
    cleaner_nav_button = ft.TextButton(text="Cleaner", icon="cleaning_services", data=1, on_click=handle_view_change, style=ft.ButtonStyle())
    navigation_row = ft.Row([search_nav_button, cleaner_nav_button], alignment=ft.MainAxisAlignment.CENTER, spacing=20)

    page.appbar = ft.AppBar(leading=ft.Icon("camera_alt"), title=ft.Text("ScreenScorch"), actions=[
        ft.PopupMenuButton(items=[
            ft.PopupMenuItem(text="Re-run Indexer", on_click=lambda e: run_task_in_thread(build_text_index, os.path.expanduser("~/Desktop"))),
            ft.PopupMenuItem(text="Re-run Embedder", on_click=lambda e: run_task_in_thread(build_semantic_index)),
        ])
    ])
    page.add(
        ft.Column([
            ft.Container(content=ft.Stack(controls=[search_view, cleaner_view]), expand=True, padding=ft.padding.all(15)),
            ft.Divider(height=1),
            ft.Container(content=navigation_row, padding=ft.padding.symmetric(vertical=5)),
            ft.Container(content=status_bar, padding=ft.padding.only(left=15, bottom=5, right=15))
        ], expand=True)
    )

ft.app(target=main)