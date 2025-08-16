import os
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

import flet as ft
import subprocess
import threading
import numpy as np
import json
from PIL import Image
from send2trash import send2trash
from core.indexer import build_master_index
from core.search_logic import perform_ultimate_search
from core.cleaner_logic import find_duplicates
from core.face_logic import load_known_faces, save_known_face

# --- MAIN APPLICATION ---
def main(page: ft.Page):
    # --- APP CONFIGURATION ---
    page.title = "ScreenScorch"
    page.window_width = 850
    page.window_height = 700
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0

    # --- STATE MANAGEMENT ---
    cleaner_checkboxes = []
    untagged_faces_cache = []

    # --- HELPER FUNCTIONS ---
    def open_file_in_finder(e, path):
        if os.path.exists(path):
            subprocess.run(["open", "-R", path])

    def move_to_trash(e, path):
        if os.path.exists(path):
            try:
                send2trash(path)
                status_bar.value = f"🗑️ Moved to Trash: {os.path.basename(path)}"
                if cleaner_view.visible: run_cleaner_scan() 
                else: handle_search(rerun=True)
            except Exception as ex:
                status_bar.value = f"❌ Error moving to Trash: {ex}"
            page.update()
    
    # --- UI CONTROLS ---
    search_field = ft.TextField(hint_text="Search by text, content, or a tagged person...", expand=True, on_submit=lambda e: handle_search())
    search_button = ft.IconButton(icon="search", on_click=lambda e: handle_search())
    results_list = ft.ListView(expand=True, spacing=5)
    search_view = ft.Column(controls=[ft.Row([search_field, search_button]), results_list], visible=True, expand=True)
    
    cleaner_results_view = ft.ListView(expand=True, spacing=15)
    delete_selected_button = ft.ElevatedButton("Move Selected to Trash", icon="delete_sweep", color="white", bgcolor="red600", height=40)
    cleaner_view = ft.Column(controls=[
        ft.Text("Duplicate & Near-Duplicate Files", size=20, weight=ft.FontWeight.BOLD),
        ft.Text("Review groups and check files to delete.", color="grey_500"), ft.Divider(),
        cleaner_results_view, ft.Container(content=delete_selected_button, alignment=ft.alignment.center)
    ], visible=False, expand=True)

    people_grid_view = ft.GridView(expand=True, max_extent=150, child_aspect_ratio=1.0, spacing=10)
    people_view = ft.Column(controls=[
        ft.Text("Untagged Faces", size=20, weight=ft.FontWeight.BOLD),
        ft.Text("Click on a face to assign a name. This name can then be used in search.", color="grey_500"), ft.Divider(),
        people_grid_view
    ], visible=False, expand=True)

    status_bar = ft.Text("Welcome! If this is your first run, please use the menu to run the Indexer.", size=12)

    # --- CORE LOGIC HANDLERS ---
    def handle_search(rerun=False):
        query = search_field.value if not rerun else getattr(search_field, 'last_query', '')
        if not query: return
        search_field.last_query = query
        status_bar.value = f"Searching for '{query}'..."
        page.update()
        results = perform_ultimate_search(query)
        results_list.controls.clear()
        if isinstance(results, dict) and "error" in results:
            status_bar.value = f"❌ Error: {results['error']}"
        elif not results:
            status_bar.value = f"🤷 No results found for '{query}'."
        else:
            for res in results:
                results_list.controls.append(create_search_result_row(res))
            status_bar.value = f"✅ Found {len(results)} results."
        page.update()

    def create_search_result_row(result_data):
        return ft.Container(
            content=ft.Row(controls=[
                ft.Image(src=result_data.get('thumbnail_path'), width=70, height=70, fit=ft.ImageFit.CONTAIN, border_radius=ft.border_radius.all(6)),
                ft.Column([
                    ft.Text(os.path.basename(result_data['file_path']), size=14, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Match: {result_data['match_type']} ({result_data['score']})", size=12, color="grey_400"),
                ], expand=True, spacing=2),
                ft.IconButton(icon="folder_open", on_click=lambda e, p=result_data['file_path']: open_file_in_finder(e, p), tooltip="Show in Finder"),
                ft.IconButton(icon="delete", on_click=lambda e, p=result_data['file_path']: move_to_trash(e, p), tooltip="Move to Trash"),
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            on_click=lambda e, p=result_data['file_path']: subprocess.run(['open', p]),
            padding=ft.padding.symmetric(vertical=5, horizontal=10), border_radius=ft.border_radius.all(8), ink=True
        )

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
        people_view.visible = (selected_index == 2)
        people_nav_button.style.bgcolor = "white10" if selected_index == 2 else None
        if selected_index == 1: run_cleaner_scan()
        if selected_index == 2: find_and_display_untagged_faces()
        page.update()

    # --- PEOPLE/TAGGER LOGIC ---
    def find_and_display_untagged_faces():
        nonlocal untagged_faces_cache
        untagged_faces_cache.clear()
        people_grid_view.controls.clear()
        status_bar.value = "Scanning for untagged faces..."
        page.update()

        def thread_target():
            try:
                with open(os.path.join(os.path.expanduser("~"), ".screenscorch", "master_index.json"), 'r') as f:
                    master_index = json.load(f)
            except FileNotFoundError:
                status_bar.value = "Master Index not found. Please run the indexer."
                page.update()
                return

            known_face_names, known_face_embeddings = load_known_faces()
            
            for item in master_index:
                if item['face_embeddings']:
                    for i, face_embedding in enumerate(item['face_embeddings']):
                        is_known = False
                        if known_face_embeddings:
                            unknown_embedding = np.array(face_embedding)
                            matches = np.linalg.norm(known_face_embeddings - unknown_embedding, axis=1) <= 0.6
                            if np.any(matches):
                                is_known = True
                        
                        if not is_known:
                            top, right, bottom, left = item['face_locations'][i]
                            pil_img = Image.open(item['file_path']).convert("RGB")
                            face_chip = pil_img.crop((left, top, right, bottom))
                            face_chip_path = os.path.join(os.path.expanduser("~"), ".screenscorch", "thumbnails", f"face_{i}_{os.path.basename(item['file_path'])}")
                            face_chip.save(face_chip_path, "JPEG")

                            untagged_faces_cache.append({
                                "face_chip_path": face_chip_path,
                                "embedding": face_embedding,
                            })
            
            page.run_thread_safe(display_face_chips)

    def display_face_chips():
        if not untagged_faces_cache:
            people_grid_view.controls.append(ft.Text("No new untagged faces found!", text_align=ft.TextAlign.CENTER))
        else:
            for face_data in untagged_faces_cache:
                people_grid_view.controls.append(
                    ft.Card(ft.Container(
                        ft.Image(src=face_data['face_chip_path'], border_radius=ft.border_radius.all(8)),
                        on_click=lambda e, fd=face_data: open_tag_dialog(fd)
                    ))
                )
        status_bar.value = f"Found {len(untagged_faces_cache)} untagged faces."
        page.update()

    def open_tag_dialog(face_data):
        name_field = ft.TextField(label="Person's Name", autofocus=True)
        
        def save_tag(e):
            name = name_field.value.strip()
            if name:
                save_known_face(name, face_data['embedding'])
                dialog.open = False
                status_bar.value = f"Saved '{name}'. Re-scan to update view."
                page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Assign a Name"),
            content=ft.Column([
                ft.Image(src=face_data['face_chip_path']),
                name_field
            ], tight=True),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: setattr(dialog, 'open', False) or page.update()),
                ft.FilledButton("Save", on_click=save_tag),
            ]
        )
        page.dialog = dialog
        dialog.open = True
        page.update()

    # --- CLEANER LOGIC ---
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
                cb = ft.Checkbox(value=is_checked, data=file_obj['file_path'])
                cleaner_checkboxes.append(cb)
                return ft.Row(controls=[
                    cb, ft.Image(src=file_obj['thumbnail_path'], width=50, height=50, fit=ft.ImageFit.CONTAIN, border_radius=ft.border_radius.all(4)),
                    ft.Text(os.path.basename(file_obj['file_path']), expand=True, size=12),
                    ft.IconButton(icon="folder_open", on_click=lambda e, p=file_obj['file_path']: open_file_in_finder(e, p), tooltip="Show in Finder"),
                    ft.IconButton(icon="open_in_new", on_click=lambda e, p=file_obj['file_path']: subprocess.run(['open', p]), tooltip="Open File"),
                ])
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
    people_nav_button = ft.TextButton(text="People", icon="face", data=2, on_click=handle_view_change, style=ft.ButtonStyle())
    navigation_row = ft.Row([search_nav_button, cleaner_nav_button, people_nav_button], alignment=ft.MainAxisAlignment.CENTER, spacing=20)

    page.appbar = ft.AppBar(
        leading=ft.Icon("camera_alt"), title=ft.Text("ScreenScorch"),
        actions=[ft.IconButton(icon="refresh", on_click=lambda e: run_task_in_thread(build_master_index, os.path.expanduser("/Users/Saurabh/Desktop/temp")), tooltip="Re-run Master Indexer")]
    )
    page.add(
        ft.Column([
            ft.Container(content=ft.Stack(controls=[search_view, cleaner_view, people_view]), expand=True, padding=ft.padding.all(15)),
            ft.Divider(height=1),
            ft.Container(content=navigation_row, padding=ft.padding.symmetric(vertical=5)),
            ft.Container(content=status_bar, padding=ft.padding.only(left=15, bottom=5, right=15))
        ], expand=True)
    )

ft.app(target=main)