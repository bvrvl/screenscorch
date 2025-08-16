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
import sys
import hashlib

# --- CONFIGURATION ---
APP_DIR = os.path.join(os.path.expanduser("~"), ".screenscorch")
MASTER_INDEX_FILE = os.path.join(APP_DIR, "master_index.json")

# A lock to make UI updates from threads safe
ui_lock = threading.Lock()

class ScreenScorchApp(ft.Stack):
    def __init__(self):
        super().__init__()
        self.expand = True
        self.cleaner_checkboxes = []
        self.untagged_faces_cache = []

    def build(self):
        # --- EMPTY STATE VIEW ---
        self.empty_state_view = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(name="camera_enhance_sharp", size=80, color="grey600"),
                    ft.Text("Welcome to ScreenScorch", size=32, weight=ft.FontWeight.BOLD),
                    ft.Text("Your intelligent screenshot and photo manager.", size=16, color="grey500"),
                    ft.Container(height=20),
                    ft.ElevatedButton("Import your first folder to get started", icon="folder_open", on_click=self.open_folder_browser, height=50),
                    ft.Text("or", color="grey600"),
                    ft.TextButton("Scan all photos on this computer (takes a long time)", on_click=self.show_import_all_dialog),
                ],
                spacing=10, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            expand=True, alignment=ft.alignment.center, visible=False
        )

        # --- MAIN APPLICATION VIEW ---
        self.search_field = ft.TextField(hint_text="Search by text, content, or a tagged person...", expand=True, on_submit=self.handle_search)
        self.search_button = ft.IconButton(icon="search", on_click=self.handle_search)
        self.results_list = ft.ListView(expand=True, spacing=5, auto_scroll=False)
        
        # UX FIX: Create a container for progress indication
        self.progress_view = ft.Column(
            [
                ft.Text("Indexing in progress, please wait...", size=16, weight=ft.FontWeight.BOLD),
                ft.ProgressBar(width=400),
            ],
            spacing=15, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            visible=False # Initially hidden
        )
        
        # UX FIX: Put the results list and progress view in a Stack to overlay them
        self.search_results_area = ft.Stack(
            [self.results_list, self.progress_view],
            expand=True
        )

        self.search_view = ft.Column(controls=[ft.Row([self.search_field, self.search_button]), self.search_results_area], visible=True, expand=True)
        
        self.cleaner_results_view = ft.ListView(expand=True, spacing=15, auto_scroll=False)
        self.delete_selected_button = ft.ElevatedButton("Move Selected to Trash", icon="delete_sweep", color="white", bgcolor="red600", on_click=self.delete_selected_files, height=40)
        self.cleaner_view = ft.Column(controls=[ft.Text("Duplicate & Near-Duplicate Files", size=20, weight=ft.FontWeight.BOLD),ft.Text("Review groups and check files to delete.", color="grey500"), ft.Divider(),self.cleaner_results_view, ft.Container(content=self.delete_selected_button, alignment=ft.alignment.center)], visible=False, expand=True)

        self.people_grid_view = ft.GridView(expand=True, max_extent=150, child_aspect_ratio=1.0, spacing=10, run_spacing=10)
        self.people_view = ft.Column(controls=[ft.Text("Untagged Faces", size=20, weight=ft.FontWeight.BOLD),ft.Text("Click on a face to assign a name. This name can then be used in search.", color="grey500"), ft.Divider(),self.people_grid_view], visible=False, expand=True)

        self.status_bar = ft.Text("Ready.", size=12)
        self.search_nav_button = ft.TextButton(text="Search", icon="search", data=0, on_click=self.handle_view_change, style=ft.ButtonStyle(bgcolor="white10"))
        self.cleaner_nav_button = ft.TextButton(text="Cleaner", icon="cleaning_services", data=1, on_click=self.handle_view_change, style=ft.ButtonStyle())
        self.people_nav_button = ft.TextButton(text="People", icon="face", data=2, on_click=self.handle_view_change, style=ft.ButtonStyle())
        navigation_row = ft.Row([self.search_nav_button, self.cleaner_nav_button, self.people_nav_button], alignment=ft.MainAxisAlignment.CENTER, spacing=20)
        main_content_area = ft.Container(content=ft.Column(controls=[self.search_view, self.cleaner_view, self.people_view], expand=True),expand=True,padding=ft.padding.all(15))
        self.main_app_view = ft.Column(controls=[main_content_area,ft.Divider(height=1),ft.Container(content=navigation_row, padding=ft.padding.symmetric(vertical=5)),ft.Container(content=self.status_bar, padding=ft.padding.only(left=15, bottom=5, right=15))],expand=True,visible=False)

        # --- MANUAL DIALOGS AND OVERLAYS ---
        self._build_face_tag_dialog()
        self._build_import_all_dialog()
        self._build_folder_browser()

        self.controls = [
            self.main_app_view,
            self.empty_state_view,
            self.face_tag_dialog,
            self.import_all_dialog,
            self.folder_browser_view
        ]

    def _build_face_tag_dialog(self):
        self.dialog_name_field = ft.TextField(label="Person's Name", autofocus=True)
        self.dialog_face_image = ft.Image()
        self.face_tag_dialog = ft.Container(content=ft.Card(width=300, elevation=30, content=ft.Container(content=ft.Column([ft.Text("Assign a Name", size=18, weight=ft.FontWeight.BOLD), self.dialog_face_image, self.dialog_name_field, ft.Row(controls=[ft.TextButton("Cancel", on_click=self.close_tag_dialog), ft.FilledButton("Save", on_click=self.save_tag)], alignment=ft.MainAxisAlignment.END)], spacing=15), padding=20)), alignment=ft.alignment.center, visible=False, bgcolor="#99000000", expand=True)

    def _build_import_all_dialog(self):
        CONFIRMATION_TEXT = "import all photos on this computer"
        self.import_all_textfield = ft.TextField(on_change=self.on_import_all_textfield_change, autofocus=True)
        self.import_all_confirm_button = ft.ElevatedButton("Confirm and Start Scan", on_click=self.run_full_system_scan, disabled=True)
        self.import_all_dialog = ft.Container(content=ft.Card(width=450, elevation=30, content=ft.Container(content=ft.Column([ft.Text("⚠️ Full Computer Scan", weight=ft.FontWeight.BOLD, size=18), ft.Text("This will search your entire computer for image files and index them."), ft.Text("This is a very heavy operation that can take hours and consume significant resources.", weight=ft.FontWeight.BOLD), ft.Text("\nTo confirm, please type the following exactly:"), ft.Text(f"'{CONFIRMATION_TEXT}'", selectable=True), self.import_all_textfield, ft.Row([ft.TextButton("Cancel", on_click=self.close_import_all_dialog), self.import_all_confirm_button], alignment=ft.MainAxisAlignment.END)], spacing=10), padding=20)), alignment=ft.alignment.center, visible=False, bgcolor="#99000000", expand=True)

    def _build_folder_browser(self):
        self.browser_current_path = ft.Text(weight=ft.FontWeight.BOLD)
        self.browser_files_list = ft.ListView(expand=True, spacing=5, padding=10)
        self.folder_browser_view = ft.Container(content=ft.Card(elevation=30, margin=ft.margin.symmetric(horizontal=40, vertical=60), content=ft.Column([ft.Container(self.browser_current_path, padding=10, bgcolor="white10"), self.browser_files_list, ft.Row([ft.TextButton("Cancel", on_click=self.close_folder_browser), ft.ElevatedButton("Select This Folder", icon="check_circle", on_click=self.select_folder_and_start_indexing)], alignment=ft.MainAxisAlignment.END, spacing=10)], spacing=0)), visible=False, bgcolor="#99000000", expand=True)

    def did_mount(self):
        self.check_initial_state()

    def check_initial_state(self):
        try:
            if os.path.exists(MASTER_INDEX_FILE) and os.path.getsize(MASTER_INDEX_FILE) > 2:
                with open(MASTER_INDEX_FILE, 'r') as f: data = json.load(f)
                if data:
                    self.show_main_view()
                else: raise FileNotFoundError
            else: raise FileNotFoundError
        except (FileNotFoundError, json.JSONDecodeError):
            self.show_empty_view()
        self.update()

    # UX FIX: New helper functions to manage view states
    def show_empty_view(self):
        self.main_app_view.visible = False
        self.empty_state_view.visible = True

    def show_main_view(self, show_progress=False):
        self.main_app_view.visible = True
        self.empty_state_view.visible = False
        self.progress_view.visible = show_progress
        self.results_list.visible = not show_progress

    # --- IN-APP BROWSER LOGIC ---
    def open_folder_browser(self, e):
        start_path = os.path.expanduser("~")
        self._load_directory(start_path)
        self.folder_browser_view.visible = True
        self.update()

    def _load_directory(self, path):
        self.browser_current_path.value = path
        self.browser_files_list.controls.clear()
        try:
            parent = os.path.dirname(path)
            if parent and parent != path:
                self.browser_files_list.controls.append(ft.TextButton("⬆️ ..", on_click=lambda _, p=parent: self._load_directory(p), style=ft.ButtonStyle(color="amber")))
            for name in sorted(os.listdir(path)):
                full_path = os.path.join(path, name)
                if not name.startswith('.') and os.path.isdir(full_path):
                    self.browser_files_list.controls.append(ft.TextButton(f"📁 {name}", on_click=lambda _, p=full_path: self._load_directory(p)))
        except PermissionError:
            self.browser_files_list.controls.append(ft.Text("🚫 Access Denied", color="red"))
        if self.page: self.page.update()

    def select_folder_and_start_indexing(self, e):
        # UX FIX: This is the new UX flow
        selected_path = self.browser_current_path.value
        self.close_folder_browser(e) # Close the browser immediately

        if selected_path:
            self.show_main_view(show_progress=True) # Switch to main view and show progress bar
            self.update()

            def on_indexing_complete():
                # This function will be called by the indexer thread when it finishes
                self.progress_view.visible = False
                self.results_list.visible = True
                if self.page:
                    self.page.update()

            thread = threading.Thread(
                target=build_master_index, 
                args=(selected_path, on_indexing_complete, self.update_status)
            )
            thread.start()

    def close_folder_browser(self, e):
        self.folder_browser_view.visible = False
        self.update()
    
    # --- IMPORT ALL DIALOG LOGIC ---
    def show_import_all_dialog(self, e):
        self.import_all_textfield.value = ""
        self.import_all_confirm_button.disabled = True
        self.import_all_dialog.visible = True
        self.update()

    def close_import_all_dialog(self, e):
        self.import_all_dialog.visible = False
        self.update()

    def on_import_all_textfield_change(self, e):
        self.import_all_confirm_button.disabled = e.control.value.lower() != "import all photos on this computer"
        self.update()

    def run_full_system_scan(self, e):
        self.close_import_all_dialog(e)
        self.show_main_view(show_progress=True)
        self.update()

        def on_indexing_complete():
            self.progress_view.visible = False
            self.results_list.visible = True
            if self.page: self.page.update()

        def thread_target():
            if sys.platform != "darwin":
                self.update_status("❌ 'Import All' is only supported on macOS currently.")
                on_indexing_complete()
                return
            try:
                self.update_status("Using Spotlight to find all images...")
                process = subprocess.run(['mdfind', "kMDItemKind == 'Image'"], capture_output=True, text=True, check=True)
                all_image_paths = process.stdout.strip().split('\n')
                if not all_image_paths or (len(all_image_paths) == 1 and not all_image_paths[0]):
                    self.update_status("🤷 No images found by Spotlight.")
                    on_indexing_complete()
                    return
                self.update_status(f"Found {len(all_image_paths)} images. Starting indexer...")
                build_master_index(all_image_paths, on_indexing_complete, self.update_status)
            except Exception as ex:
                self.update_status(f"❌ An error occurred during full scan: {ex}")
                on_indexing_complete()
        
        threading.Thread(target=thread_target).start()
        
    def open_tag_dialog(self, face_data):
        self.current_face_data = face_data
        self.dialog_face_image.src = face_data['face_chip_path']
        self.dialog_name_field.value = ""
        self.face_tag_dialog.visible = True
        self.update()

    def close_tag_dialog(self, e):
        self.face_tag_dialog.visible = False
        self.update()
        
    def save_tag(self, e):
        name = self.dialog_name_field.value.strip()
        if name and hasattr(self, 'current_face_data'):
            save_known_face(name, self.current_face_data['embedding'])
            self.update_status(f"✅ Saved '{name}'. Re-scanning faces...")
            self.find_and_display_untagged_faces()
        self.face_tag_dialog.visible = False
        self.update()

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
        self.update()

    def create_face_card(self, face_data):
        return ft.Container(content=ft.Card(elevation=4, content=ft.Image(src=face_data['face_chip_path'], border_radius=ft.border_radius.all(8), fit=ft.ImageFit.COVER, width=150, height=150)), on_click=lambda e: self.open_tag_dialog(face_data), ink=True, border_radius=ft.border_radius.all(8))
    
    def find_and_display_untagged_faces(self):
        self.people_grid_view.controls.clear()
        self.update_status("Scanning for untagged faces...")
        def thread_target():
            try:
                with open(MASTER_INDEX_FILE, 'r') as f: master_index = json.load(f)
                known_face_names, known_face_embeddings = load_known_faces()
                temp_untagged_faces = []
                for item in master_index:
                    if not item.get('face_embeddings'): continue
                    for i, face_embedding in enumerate(item['face_embeddings']):
                        is_known = False
                        if known_face_embeddings:
                            matches = np.linalg.norm(np.array(known_face_embeddings) - np.array(face_embedding), axis=1) <= 0.6
                            if np.any(matches): is_known = True
                        if not is_known:
                            temp_untagged_faces.append({"item_data": item, "face_index": i, "embedding": face_embedding})
                new_face_cache = []
                for face_data in temp_untagged_faces:
                    item, i = face_data['item_data'], face_data['face_index']
                    thumb_img = Image.open(item['thumbnail_path'])
                    face_locations = item.get('face_locations', [])
                    if i < len(face_locations):
                        top, right, bottom, left = face_locations[i]
                        orig_w, orig_h = item['width'], item['height']
                        thumb_w, thumb_h = thumb_img.size
                        x_scale, y_scale = thumb_w / orig_w, thumb_h / orig_h
                        thumb_coords = (int(left * x_scale), int(top * y_scale), int(right * x_scale), int(bottom * y_scale))
                        face_chip = thumb_img.crop(thumb_coords)
                        face_chip_filename = f"{hashlib.md5(item['file_path'].encode()).hexdigest()}_face_{i}.jpeg"
                        face_chip_path = os.path.join(APP_DIR, "thumbnails", face_chip_filename)
                        face_chip.save(face_chip_path, "JPEG")
                        new_face_cache.append({"face_chip_path": face_chip_path, "embedding": face_data['embedding']})
                self.display_face_chips(new_face_cache)
            except Exception as e:
                self.update_status(f"❌ Error scanning faces: {e}")
        threading.Thread(target=thread_target).start()

    def display_face_chips(self, face_cache):
        with ui_lock:
            self.untagged_faces_cache = face_cache
            self.people_grid_view.controls.clear()
            if not self.untagged_faces_cache:
                message = ft.Text("No new untagged faces found!", text_align=ft.TextAlign.CENTER)
                self.people_grid_view.controls.append(ft.Container(content=message, alignment=ft.alignment.center, expand=True))
            else:
                for face_data in self.untagged_faces_cache: self.people_grid_view.controls.append(self.create_face_card(face_data))
            self.status_bar.value = f"Displaying {len(self.untagged_faces_cache)} untagged faces."
            if self.page: self.page.update()
    
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
                for res in results: self.results_list.controls.append(self.create_search_result_row(res))
                self.status_bar.value = f"✅ Found {len(results)} results."
            self.page.update()

    def create_search_result_row(self, result_data):
        return ft.Container(content=ft.Row(controls=[ft.Image(src=result_data.get('thumbnail_path'), width=70, height=70, fit=ft.ImageFit.CONTAIN, border_radius=ft.border_radius.all(6)),ft.Column([ft.Text(os.path.basename(result_data['file_path']), size=14, weight=ft.FontWeight.BOLD),ft.Text(f"Match: {result_data['match_type']} ({result_data['score']})", size=12, color="grey400"),], expand=True, spacing=2),ft.IconButton(icon="folder_open", on_click=lambda e, p=result_data['file_path']: self.open_file_in_finder(e, p), tooltip="Show in Finder"),ft.IconButton(icon="delete", on_click=lambda e, p=result_data['file_path']: self.move_to_trash(e, p), tooltip="Move to Trash"),], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),on_click=lambda e, p=result_data['file_path']: subprocess.run(['open', p]),padding=ft.padding.symmetric(vertical=5, horizontal=10), border_radius=ft.border_radius.all(8), ink=True)

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
        
    def delete_selected_files(self, e):
        files_to_delete = [cb.data for cb in self.cleaner_checkboxes if cb.value]
        if not files_to_delete:
            self.update_status("No files selected to delete.")
            return
        for path in files_to_delete: self.move_to_trash(None, path)
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
                    return ft.Row(controls=[cb, ft.Image(src=file_obj['thumbnail_path'], width=50, height=50, fit=ft.ImageFit.CONTAIN, border_radius=ft.border_radius.all(4)),ft.Text(os.path.basename(file_obj['file_path']), expand=True, size=12),ft.IconButton(icon="folder_open", on_click=lambda e, p=file_obj['file_path']: self.open_file_in_finder(e, p), tooltip="Show in Finder"),ft.IconButton(icon="open_in_new", on_click=lambda e, p=file_obj['file_path']: subprocess.run(['open', p]), tooltip="Open File"),])
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

    # Build the AppBar and wire its buttons to the app's methods
    page.appbar = ft.AppBar(
        leading=ft.Icon("camera_alt"), 
        title=ft.Text("ScreenScorch"),
        actions=[
            ft.PopupMenuButton(
                items=[
                    ft.PopupMenuItem(
                        text="Import Folder...", 
                        icon="folder_open",
                        on_click=app.open_folder_browser
                    ),
                    ft.PopupMenuItem(
                        text="Import All Photos on this Mac...", 
                        icon="devices_other",
                        on_click=app.show_import_all_dialog
                    ),
                ]
            )
        ]
    )
    
    page.add(app)

if __name__ == "__main__":
    ft.app(target=main)