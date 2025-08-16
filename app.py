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

# A lock to make UI updates from threads safe
ui_lock = threading.Lock()

class ScreenScorchApp(ft.Stack):
    def __init__(self):
        super().__init__()
        self.expand = True
        self.cleaner_checkboxes = []
        self.untagged_faces_cache = []

    def build(self):
        # --- UI CONTROLS ---
        self.search_field = ft.TextField(hint_text="Search by text, content, or a tagged person...", expand=True, on_submit=self.handle_search)
        self.search_button = ft.IconButton(icon="search", on_click=self.handle_search)
        self.results_list = ft.ListView(expand=True, spacing=5, auto_scroll=False)
        self.search_view = ft.Column(controls=[ft.Row([self.search_field, self.search_button]), self.results_list], visible=True, expand=True)
        
        self.cleaner_results_view = ft.ListView(expand=True, spacing=15, auto_scroll=False)
        self.delete_selected_button = ft.ElevatedButton("Move Selected to Trash", icon="delete_sweep", color="white", bgcolor="red600", on_click=self.delete_selected_files, height=40)
        self.cleaner_view = ft.Column(controls=[
            ft.Text("Duplicate & Near-Duplicate Files", size=20, weight=ft.FontWeight.BOLD),
            ft.Text("Review groups and check files to delete.", color="grey_500"), ft.Divider(),
            self.cleaner_results_view, ft.Container(content=self.delete_selected_button, alignment=ft.alignment.center)
        ], visible=False, expand=True)

        self.people_grid_view = ft.GridView(expand=True, max_extent=150, child_aspect_ratio=1.0, spacing=10, run_spacing=10)
        self.people_view = ft.Column(controls=[
            ft.Text("Untagged Faces", size=20, weight=ft.FontWeight.BOLD),
            ft.Text("Click on a face to assign a name. This name can then be used in search.", color="grey_500"), ft.Divider(),
            self.people_grid_view
        ], visible=False, expand=True)

        self.status_bar = ft.Text("Welcome!", size=12)

        self.search_nav_button = ft.TextButton(text="Search", icon="search", data=0, on_click=self.handle_view_change, style=ft.ButtonStyle(bgcolor="white10"))
        self.cleaner_nav_button = ft.TextButton(text="Cleaner", icon="cleaning_services", data=1, on_click=self.handle_view_change, style=ft.ButtonStyle())
        self.people_nav_button = ft.TextButton(text="People", icon="face", data=2, on_click=self.handle_view_change, style=ft.ButtonStyle())
        
        navigation_row = ft.Row([self.search_nav_button, self.cleaner_nav_button, self.people_nav_button], alignment=ft.MainAxisAlignment.CENTER, spacing=20)
        
        main_content_area = ft.Container(
            content=ft.Column(
                controls=[
                    self.search_view,
                    self.cleaner_view,
                    self.people_view,
                ],
                expand=True
            ),
            expand=True,
            padding=ft.padding.all(15)
        )

        # --- MANUAL DIALOG IMPLEMENTATION ---
        self.dialog_name_field = ft.TextField(label="Person's Name", autofocus=True)
        self.dialog_face_image = ft.Image()
        self.manual_dialog = ft.Container(
            content=ft.Card(
                width=300,
                elevation=30,
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("Assign a Name", size=18, weight=ft.FontWeight.BOLD),
                        self.dialog_face_image, 
                        self.dialog_name_field,
                        ft.Row(
                            controls=[
                                ft.TextButton("Cancel", on_click=self.close_tag_dialog),
                                ft.FilledButton("Save", on_click=self.save_tag),
                            ],
                            alignment=ft.MainAxisAlignment.END
                        )
                    ], spacing=15),
                    padding=20
                )
            ),
            alignment=ft.alignment.center,
            visible=False,
            # Using a direct RGBA hex string for 60% opacity black
            bgcolor="#99000000",
            expand=True,
        )

        main_app_column = ft.Column(
            controls=[
                main_content_area,
                ft.Divider(height=1),
                ft.Container(content=navigation_row, padding=ft.padding.symmetric(vertical=5)),
                ft.Container(content=self.status_bar, padding=ft.padding.only(left=15, bottom=5, right=15))
            ],
            expand=True
        )

        self.controls = [
            main_app_column,
            self.manual_dialog,
        ]

    # --- REWRITTEN DIALOG HANDLERS ---
    def open_tag_dialog(self, face_data):
        self.current_face_data = face_data
        self.dialog_face_image.src = face_data['face_chip_path']
        self.dialog_name_field.value = ""
        self.manual_dialog.visible = True
        self.page.update()

    def close_tag_dialog(self, e):
        self.manual_dialog.visible = False
        self.page.update()
        
    def save_tag(self, e):
        name = self.dialog_name_field.value.strip()
        if name and hasattr(self, 'current_face_data'):
            save_known_face(name, self.current_face_data['embedding'])
            self.update_status(f"✅ Saved '{name}'. Re-scanning now...")
            self.find_and_display_untagged_faces()
        
        self.manual_dialog.visible = False
        self.page.update()

    def update_status(self, message):
        with ui_lock:
            self.status_bar.value = message
            if self.page: self.page.update()

    def handle_view_change(self, e):
        selected_index = e.control.data
        self.search_view.visible = (selected_index == 0)
        self.search_nav_button.style.bgcolor = "white10" if selected_index == 0 else None
        self.cleaner_view.visible = (selected_index == 1)
        self.cleaner_nav_button.style.bgcolor = "white10" if selected_index == 1 else None
        self.people_view.visible = (selected_index == 2)
        self.people_nav_button.style.bgcolor = "white10" if selected_index == 2 else None
        
        if selected_index == 1: self.run_cleaner_scan()
        if selected_index == 2: self.find_and_display_untagged_faces()

        self.page.update()

    def create_face_card(self, face_data):
        return ft.Container(
            content=ft.Card(
                elevation=4,
                content=ft.Image(src=face_data['face_chip_path'], border_radius=ft.border_radius.all(8), fit=ft.ImageFit.COVER, width=150, height=150)
            ),
            on_click=lambda e: self.open_tag_dialog(face_data),
            ink=True,
            border_radius=ft.border_radius.all(8)
        )

    def display_face_chips(self, face_cache):
        with ui_lock:
            self.untagged_faces_cache = face_cache
            self.people_grid_view.controls.clear()
            if not self.untagged_faces_cache:
                message = ft.Text("No new untagged faces found!", text_align=ft.TextAlign.CENTER)
                self.people_grid_view.controls.append(ft.Container(content=message, alignment=ft.alignment.center, expand=True))
            else:
                for face_data in self.untagged_faces_cache:
                    self.people_grid_view.controls.append(self.create_face_card(face_data))
            self.status_bar.value = f"Displaying {len(self.untagged_faces_cache)} untagged faces."
            if self.page: self.page.update()

    def find_and_display_untagged_faces(self):
        self.people_grid_view.controls.clear()
        self.update_status("Scanning for untagged faces...")
        def thread_target():
            try:
                APP_DIR = os.path.join(os.path.expanduser("~"), ".screenscorch")
                MASTER_INDEX_FILE = os.path.join(APP_DIR, "master_index.json")
                THUMBNAIL_DIR = os.path.join(APP_DIR, "thumbnails")

                with open(MASTER_INDEX_FILE, 'r') as f: master_index = json.load(f)
                known_face_names, known_face_embeddings = load_known_faces()
                temp_untagged_faces = []
                for item in master_index:
                    if not item.get('face_embeddings'): continue
                    for i, face_embedding in enumerate(item['face_embeddings']):
                        is_known = False
                        if known_face_embeddings:
                            matches = np.linalg.norm(known_face_embeddings - np.array(face_embedding), axis=1) <= 0.6
                            if np.any(matches): is_known = True
                        if not is_known:
                            temp_untagged_faces.append({"item_data": item, "face_index": i, "embedding": face_embedding})
                
                new_face_cache = []
                for face_data in temp_untagged_faces:
                    item, i = face_data['item_data'], face_data['face_index']
                    thumb_img = Image.open(item['thumbnail_path'])
                    orig_w, orig_h = item['width'], item['height']
                    thumb_w, thumb_h = thumb_img.size
                    x_scale, y_scale = thumb_w / orig_w, thumb_h / orig_h
                    top, right, bottom, left = item['face_locations'][i]
                    thumb_coords = (int(left * x_scale), int(top * y_scale), int(right * x_scale), int(bottom * y_scale))
                    face_chip = thumb_img.crop(thumb_coords)
                    face_chip_filename = f"face_{i}_{os.path.basename(item['file_path'])}"
                    face_chip_path = os.path.join(THUMBNAIL_DIR, face_chip_filename)
                    face_chip.save(face_chip_path, "JPEG")
                    new_face_cache.append({"face_chip_path": face_chip_path, "embedding": face_data['embedding']})
                self.display_face_chips(new_face_cache)
            except Exception as e:
                self.update_status(f"❌ Error scanning faces: {e}")
        
        threading.Thread(target=thread_target).start()

    def handle_search(self, e=None, rerun=False):
        query = self.search_field.value if not rerun else getattr(self.search_field, 'last_query', '')
        if not query: return
        self.search_field.last_query = query
        self.update_status(f"Searching for '{query}'...")
        results = perform_ultimate_search(query)
        with ui_lock:
            self.results_list.controls.clear()
            if isinstance(results, dict) and "error" in results:
                self.status_bar.value = f"❌ Error: {results['error']}"
            elif not results:
                self.status_bar.value = f"🤷 No results found for '{query}'."
            else:
                for res in results:
                    self.results_list.controls.append(self.create_search_result_row(res))
                self.status_bar.value = f"✅ Found {len(results)} results."
            self.page.update()

    def create_search_result_row(self, result_data):
        return ft.Container(
            content=ft.Row(controls=[
                ft.Image(src=result_data.get('thumbnail_path'), width=70, height=70, fit=ft.ImageFit.CONTAIN, border_radius=ft.border_radius.all(6)),
                ft.Column([
                    ft.Text(os.path.basename(result_data['file_path']), size=14, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Match: {result_data['match_type']} ({result_data['score']})", size=12, color="grey_400"),
                ], expand=True, spacing=2),
                ft.IconButton(icon="folder_open", on_click=lambda e, p=result_data['file_path']: self.open_file_in_finder(e, p), tooltip="Show in Finder"),
                ft.IconButton(icon="delete", on_click=lambda e, p=result_data['file_path']: self.move_to_trash(e, p), tooltip="Move to Trash"),
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            on_click=lambda e, p=result_data['file_path']: subprocess.run(['open', p]),
            padding=ft.padding.symmetric(vertical=5, horizontal=10), border_radius=ft.border_radius.all(8), ink=True
        )

    def open_file_in_finder(self, e, path):
        if os.path.exists(path): subprocess.run(["open", "-R", path])

    def move_to_trash(self, e, path):
        if os.path.exists(path):
            try:
                send2trash(path)
                self.update_status(f"🗑️ Moved to Trash: {os.path.basename(path)}")
                if self.cleaner_view.visible: self.run_cleaner_scan() 
                else: self.handle_search(rerun=True)
            except Exception as ex:
                self.update_status(f"❌ Error moving to Trash: {ex}")

    def run_task_in_thread(self, target_func, *args):
        thread = threading.Thread(target=target_func, args=(*args, self.update_status))
        thread.start()
        
    def delete_selected_files(self, e):
        files_to_delete = [cb.data for cb in self.cleaner_checkboxes if cb.value]
        if not files_to_delete:
            self.update_status("No files selected to delete.")
            return
        
        for path in files_to_delete:
            self.move_to_trash(None, path)
        
        self.update_status(f"✅ Moved {len(files_to_delete)} files to Trash.")
        self.run_cleaner_scan()

    def run_cleaner_scan(self):
        self.cleaner_checkboxes.clear()
        self.cleaner_results_view.controls.clear()
        self.update_status("Starting duplicate scan...")
        self.page.update()

        def on_scan_complete(dupes):
            with ui_lock:
                self.cleaner_results_view.controls.clear()
                if dupes is None: return

                if not dupes["exact"] and not dupes["near"]:
                    self.cleaner_results_view.controls.append(ft.Text("No duplicates found!", italic=True, text_align=ft.TextAlign.CENTER))
                
                def create_file_row(file_obj, is_checked):
                    cb = ft.Checkbox(value=is_checked, data=file_obj['file_path'])
                    self.cleaner_checkboxes.append(cb)
                    return ft.Row(controls=[
                        cb, ft.Image(src=file_obj['thumbnail_path'], width=50, height=50, fit=ft.ImageFit.CONTAIN, border_radius=ft.border_radius.all(4)),
                        ft.Text(os.path.basename(file_obj['file_path']), expand=True, size=12),
                        ft.IconButton(icon="folder_open", on_click=lambda e, p=file_obj['file_path']: self.open_file_in_finder(e, p), tooltip="Show in Finder"),
                        ft.IconButton(icon="open_in_new", on_click=lambda e, p=file_obj['file_path']: subprocess.run(['open', p]), tooltip="Open File"),
                    ])

                if dupes["exact"]:
                    self.cleaner_results_view.controls.append(ft.Text("Exact Duplicates", weight=ft.FontWeight.BOLD))
                    for group in dupes["exact"]:
                        group_col = ft.Column([create_file_row(file, i > 0) for i, file in enumerate(group)])
                        self.cleaner_results_view.controls.append(ft.Card(content=ft.Container(group_col, padding=10)))
                
                if dupes["near"]:
                    self.cleaner_results_view.controls.append(ft.Container(ft.Text("Near Duplicates", weight=ft.FontWeight.BOLD), margin=ft.margin.only(top=20)))
                    for group in dupes["near"]:
                        group_col = ft.Column([create_file_row(file, i > 0) for i, file in enumerate(group)])
                        self.cleaner_results_view.controls.append(ft.Card(content=ft.Container(group_col, padding=10)))
                
                self.update_status("✅ Duplicate scan complete.")
                if self.page: self.page.update()

        def final_scanner_thread_target():
            duplicate_data = find_duplicates(self.update_status)
            on_scan_complete(duplicate_data)
        
        threading.Thread(target=final_scanner_thread_target).start()

# --- MAIN FUNCTION TO START THE APP ---
def main(page: ft.Page):
    page.title = "ScreenScorch"
    page.window_width = 850
    page.window_height = 700
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0

    app = ScreenScorchApp()

    screenshots_path = os.path.expanduser("~/Desktop")

    page.appbar = ft.AppBar(
        leading=ft.Icon("camera_alt"), title=ft.Text("ScreenScorch"),
        actions=[ft.IconButton(icon="refresh", on_click=lambda e: app.run_task_in_thread(build_master_index, screenshots_path), tooltip="Re-run Master Indexer")]
    )
    page.add(app)
    page.update()

if __name__ == "__main__":
    ft.app(target=main)