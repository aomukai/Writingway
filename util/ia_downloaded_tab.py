from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QComboBox, QDateEdit, QCheckBox, QTreeView, QFileSystemModel, QMessageBox, QAbstractItemView, QMenu, QDialog, QScrollArea, QTextEdit, QShortcut, QHeaderView
from PyQt5.QtCore import Qt, QItemSelectionModel, QUrl, QDate, QObject, pyqtSignal
from PyQt5.QtGui import QPixmap, QDesktopServices, QImage, QKeySequence, QTextDocument, QTextCursor
from settings.theme_manager import ThemeManager
from workshop.rag_pdf import PdfRagApp
from util.whisper_app import WhisperApp
from pathlib import Path
import os
import datetime
import shutil
import fnmatch
import fitz
import logging

# Set up logging
logger = logging.getLogger(__name__)

class DocumentRenderer(QObject):
    """Class to handle document rendering with PyMuPDF."""
    page_rendered = pyqtSignal(QPixmap, int, int)
    render_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.doc = None
        self.zoom_level = 1.5  # Default zoom level

    def load_document(self, file_path, filetype=None):
        """Load a document from a file path."""
        try:
            self.doc = fitz.open(file_path, filetype=filetype)
            return True
        except Exception as e:
            self.render_error.emit(f"Failed to load document: {str(e)}")
            return False

    def render_page(self, page_num):
        """Render a specific page at the current zoom level."""
        try:
            if not self.doc or page_num < 0 or page_num >= self.doc.page_count:
                self.render_error.emit("Invalid page number or document not loaded")
                return

            page = self.doc[page_num]
            matrix = fitz.Matrix(self.zoom_level, self.zoom_level)
            pix = page.get_pixmap(matrix=matrix)
            
            # Convert to QImage and then to QPixmap
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(img)
            
            # Emit the rendered page
            self.page_rendered.emit(pixmap, page_num, self.doc.page_count)
        except Exception as e:
            self.render_error.emit(f"Error rendering page: {str(e)}")

    def set_zoom(self, new_zoom):
        """Set a new zoom level."""
        self.zoom_level = new_zoom

    def close(self):
        """Close the document and free resources."""
        if self.doc:
            self.doc.close()
            self.doc = None

class DownloadedTab(QWidget):
    def __init__(self, download_dir, parent=None):
        super().__init__(parent)
        self.download_dir = download_dir
        
        # Initialize tracking for active filters
        self.active_filters = {
            "text_filter": [],
            "type_filter": [],
            "date_filter": {"enabled": False, "files": []}
        }
        
        # Dictionary to store original filter state
        self.original_filter_state = {
            "name_filters": None,
            "name_filter_enabled": None
        }
        
        # Initialize the UI
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Filter section
        filter_layout = QHBoxLayout()

        # Simple text filter
        self.file_filter_input = QLineEdit()
        self.file_filter_input.setPlaceholderText("Filter by name (e.g. *.pdf, report)")
        self.file_filter_btn = QPushButton("Apply Filter")
        self.file_filter_btn.clicked.connect(self.apply_file_filter)
        self.clear_filter_btn = QPushButton("Clear Filter")
        self.clear_filter_btn.clicked.connect(self.clear_file_filter)

        filter_layout.addWidget(self.file_filter_input)
        filter_layout.addWidget(self.file_filter_btn)
        filter_layout.addWidget(self.clear_filter_btn)

        # Advanced filter section
        advanced_filter_layout = QHBoxLayout()

        # File type filter
        self.file_type_filter = QComboBox()
        self.file_type_filter.addItems(["All Files", "Images (*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.svg *.webp *.ico *.heic *.raw)",
                                        "Ebooks (*.epub *.mobi *.fb2 *.pdf *.xps)",
                                        "Documents (*.txt *.md *.tex *.doc *.docx *.odt *.rtf)",
                                        "Audio (*.mp3 *.wav *.ogg *.flac *.aac *.wma *.m4a *.opus)",
                                        "Video (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.mpeg *.mpg)",
                                        "Archive (*.zip *.rar *.7z *.tar *.gz *.bz2 *.iso *.xz)",
                                        "Other (*.sqlite *.torrent *.csv *.xml *.json *.html *.htm)"])
        self.file_type_filter.currentIndexChanged.connect(self.apply_type_filter)

        # Date filter
        self.date_filter_layout = QHBoxLayout()
        self.date_filter_check = QCheckBox("Filter by date:")
        self.date_from_filter = QDateEdit()
        self.date_from_filter.setDate(QDate.currentDate().addDays(-30))
        self.date_to_filter = QDateEdit()
        self.date_to_filter.setDate(QDate.currentDate())
        self.apply_date_filter_btn = QPushButton("Apply Date Filter")
        self.apply_date_filter_btn.clicked.connect(self.apply_date_filter)

        self.date_filter_layout.addWidget(self.date_filter_check)
        self.date_filter_layout.addWidget(QLabel("From:"))
        self.date_filter_layout.addWidget(self.date_from_filter)
        self.date_filter_layout.addWidget(QLabel("To:"))
        self.date_filter_layout.addWidget(self.date_to_filter)
        self.date_filter_layout.addWidget(self.apply_date_filter_btn)

        advanced_filter_layout.addWidget(QLabel("File Type:"))
        advanced_filter_layout.addWidget(self.file_type_filter)

        # Tree view for downloaded files with selection mode
        self.downloaded_tree = QTreeView()
        self.downloaded_model = QFileSystemModel()
        self.downloaded_model.setRootPath(str(self.download_dir))
        self.downloaded_tree.setModel(self.downloaded_model)
        self.downloaded_tree.setRootIndex(self.downloaded_model.index(str(self.download_dir)))
        self.downloaded_tree.setSortingEnabled(True)
        self.downloaded_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.downloaded_tree.doubleClicked.connect(self.open_downloaded_file)
        
        # Set the Name column width to be wider than others
        self.downloaded_tree.header().setStretchLastSection(False)
        self.downloaded_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)  # Make Name column stretch
        for i in range(1, self.downloaded_model.columnCount()):
            self.downloaded_tree.header().setSectionResizeMode(i, QHeaderView.ResizeToContents)

        # Set up context menu for the tree view
        self.downloaded_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.downloaded_tree.customContextMenuRequested.connect(self.show_context_menu)

        # File management buttons
        file_management_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_file_tree)
        self.select_all_files_btn = QPushButton("Select All Filtered")
        self.select_all_files_btn.clicked.connect(self.select_all_filtered_files)
        self.remove_empty_folders_btn = QPushButton("Remove Empty Folders")
        self.remove_empty_folders_btn.clicked.connect(self.remove_empty_folders)
        self.delete_selected_btn = QPushButton("Delete Selected")
        self.delete_selected_btn.clicked.connect(self.delete_selected_files)

        # Tools buttons layout
        tools_layout = QHBoxLayout()
        
        # PDF RAG Button
        self.pdf_rag_btn = QPushButton()
        self.pdf_rag_btn.setIcon(ThemeManager.get_tinted_icon("assets/icons/file-text.svg"))
        self.pdf_rag_btn.setToolTip("Document Analysis (PDF/Images)")
        self.pdf_rag_btn.clicked.connect(self.open_pdf_rag_tool)
        
        # Whisper App Button
        self.whisper_app_btn = QPushButton()
        self.whisper_app_btn.setIcon(ThemeManager.get_tinted_icon("assets/icons/mic.svg"))
        self.whisper_app_btn.setToolTip("Open Whisper")
        self.whisper_app_btn.clicked.connect(self.open_whisper_app)
        
        tools_layout.addWidget(self.pdf_rag_btn)
        tools_layout.addWidget(self.whisper_app_btn)
        tools_layout.addStretch()  # Add stretch to push buttons to the left
        
        file_management_layout.addWidget(self.refresh_btn)
        file_management_layout.addWidget(self.select_all_files_btn)
        file_management_layout.addWidget(self.remove_empty_folders_btn)
        file_management_layout.addWidget(self.delete_selected_btn)

        # Add all components to the main layout
        layout.addWidget(QLabel("Filter Files:"))
        layout.addLayout(filter_layout)
        layout.addLayout(advanced_filter_layout)
        layout.addLayout(self.date_filter_layout)
        layout.addWidget(QLabel("Downloaded Files:"))
        layout.addWidget(self.downloaded_tree)
        layout.addLayout(file_management_layout)
        layout.addWidget(QLabel("Tools:"))
        layout.addLayout(tools_layout)

        # Store the original filter state
        self.original_filter_state = {
            "name_filters": [],
            "name_filter_enabled": False
        }

    def open_pdf_rag_tool(self):
        """Open the PDF RAG processor as independent window"""
        self.pdf_window = PdfRagApp()
        self.pdf_window.show()

    def open_whisper_app(self):
        """Open the WhisperApp as independent window"""
        self.whisper_app = WhisperApp()
        self.whisper_app.show()

    def apply_file_filter(self):
        """Apply text filter to the file system model."""
        filter_text = self.file_filter_input.text().strip()
        if filter_text:
            if not self.original_filter_state.get("name_filters"):
                self.original_filter_state["name_filters"] = self.downloaded_model.nameFilters()
                self.original_filter_state["name_filter_enabled"] = self.downloaded_model.nameFilterDisables()
            
            if "," in filter_text:
                filters = [pattern.strip() for pattern in filter_text.split(",")]
            else:
                if "*" not in filter_text:
                    filters = [f"*{filter_text}*"]
                else:
                    filters = [filter_text]
            
            # Store the text filter
            self.active_filters["text_filter"] = filters
            
            # Apply combined filters
            self._apply_combined_filters()
            QMessageBox.information(self, "Filter Applied", f"Showing files matching: {filter_text}")
        else:
            QMessageBox.warning(self, "Filter Error", "Please enter a filter pattern.")

    def clear_file_filter(self):
        """Clear all filters and show all files."""
        self.file_filter_input.clear()
        self.file_type_filter.setCurrentIndex(0)
        self.date_filter_check.setChecked(False)
        
        # Reset all active filters
        self.active_filters = {
            "text_filter": [],
            "type_filter": [],
            "date_filter": {"enabled": False, "files": []}
        }

        self.downloaded_model.setNameFilters([])
        self.downloaded_model.setNameFilterDisables(True)

        try:
            current_path = self.downloaded_model.rootPath()
            self.downloaded_model.setRootPath("")
            self.downloaded_model.setRootPath(current_path)
            QMessageBox.information(self, "Filters Cleared", "All filters have been removed.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to refresh file list: {str(e)}")

    def apply_type_filter(self, index):
        """Apply file type filter based on selection."""
        filter_patterns = []
        
        if index == 0:  # "All Files" option
            self.active_filters["type_filter"] = []
        elif index == 1:  # Images
            filter_patterns = ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp", "*.tiff", "*.svg", "*.webp", "*.ico", "*.heic", "*.raw"]
        elif index == 2:  # Ebooks
            filter_patterns = ["*.epub", "*.mobi", "*.fb2", "*.pdf", "*.xps"]
        elif index == 3:  # Documents
            filter_patterns = ["*.txt", "*.md", "*.tex", "*.doc", "*.docx", "*.odt", "*.rtf"]
        elif index == 4:  # Audio
            filter_patterns = ["*.mp3", "*.wav", "*.ogg", "*.flac", "*.aac", "*.wma", "*.m4a", "*.opus"]
        elif index == 5:  # Video
            filter_patterns = ["*.mp4", "*.avi", "*.mkv", "*.mov", "*.wmv", "*.flv", "*.webm", "*.mpeg", "*.mpg"]
        elif index == 6:  # Archive
            filter_patterns = ["*.zip", "*.rar", "*.7z", "*.tar", "*.gz", "*.bz2", "*.iso", "*.xz"]
        elif index == 7:  # Other
            filter_patterns = ["*.sqlite", "*.torrent", "*.csv", "*.xml", "*.json", "*.html", "*.htm"]

        # Update the type filter
        self.active_filters["type_filter"] = filter_patterns
        
        # Apply combined filters
        self._apply_combined_filters()

    def apply_date_filter(self):
        """Filter files based on modification date range."""
        if not self.date_filter_check.isChecked():
            self.active_filters["date_filter"]["enabled"] = False
            self.active_filters["date_filter"]["files"] = []
            self._apply_combined_filters()
            return
        
        from_date = self.date_from_filter.date().toPyDate()
        to_date = self.date_to_filter.date().toPyDate()
        
        filtered_files = []
        
        try:
            root_path = str(self.download_dir)
            for file_path in Path(root_path).rglob('*'):
                if file_path.is_file():
                    mod_time = datetime.datetime.fromtimestamp(file_path.stat().st_mtime).date()
                    if from_date <= mod_time <= to_date:
                        filtered_files.append(file_path.name)
            
            # Store date filter results
            self.active_filters["date_filter"]["enabled"] = True
            self.active_filters["date_filter"]["files"] = filtered_files
            
            # Apply combined filters
            self._apply_combined_filters()
            
            QMessageBox.information(self, "Date Filter Applied", f"Found {len(filtered_files)} files modified between {from_date} and {to_date}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error applying date filter: {str(e)}")
            
    def _apply_combined_filters(self):
        """Apply all active filters together."""
        combined_patterns = []
        
        # Logic for combining filters:
        # 1. Start with text filter if present
        # 2. Intersect with type filter if present
        # 3. Further intersect with date filter files if enabled
        
        if self.active_filters["text_filter"] and self.active_filters["type_filter"]:
            # We need to combine text and type filters
            # For each text pattern, combine with each type pattern
            for text_pattern in self.active_filters["text_filter"]:
                for type_pattern in self.active_filters["type_filter"]:
                    # Remove asterisks and combine patterns correctly
                    if text_pattern == "*" or type_pattern == "*":
                        combined_patterns.append(text_pattern if type_pattern == "*" else type_pattern)
                    else:
                        text_base = text_pattern.replace("*", "")
                        type_extension = type_pattern.replace("*", "")
                        combined_patterns.append(f"*{text_base}*{type_extension}")
        elif self.active_filters["text_filter"]:
            combined_patterns = self.active_filters["text_filter"]
        elif self.active_filters["type_filter"]:
            combined_patterns = self.active_filters["type_filter"]
        
        # Apply filters
        if combined_patterns:
            self.downloaded_model.setNameFilters(combined_patterns)
            self.downloaded_model.setNameFilterDisables(False)
        else:
            self.downloaded_model.setNameFilters([])
            self.downloaded_model.setNameFilterDisables(True)
        
        # If date filter is enabled, we need to further filter the results
        if self.active_filters["date_filter"]["enabled"] and self.active_filters["date_filter"]["files"]:
            # Apply date filter on top of other filters
            if combined_patterns:
                # We need to find files that match both the patterns and are in the date filter list
                # This is complex and might require custom proxy model. For now, we'll just use the date filenames
                self.downloaded_model.setNameFilters(self.active_filters["date_filter"]["files"])
                self.downloaded_model.setNameFilterDisables(False)
            else:
                self.downloaded_model.setNameFilters(self.active_filters["date_filter"]["files"])
                self.downloaded_model.setNameFilterDisables(False)

    def refresh_file_tree(self):
        """Refresh the file tree view to show any changes."""
        try:
            current_path = self.downloaded_model.rootPath()
            self.downloaded_model.setRootPath("")
            self.downloaded_model.setRootPath(current_path)
            QMessageBox.information(self, "Refreshed", "File list has been refreshed.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to refresh file list: {str(e)}")

    def select_all_filtered_files(self):
        """Select all currently visible files in the tree view."""
        try:
            root_path = str(self.download_dir)
            filters = self.downloaded_model.nameFilters()
            self.downloaded_tree.clearSelection()

            for root, unused, files in os.walk(root_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if not filters or any(fnmatch.fnmatch(file, f) for f in filters):
                        index = self.downloaded_model.index(file_path)
                        self.downloaded_tree.selectionModel().select(index, QItemSelectionModel.Select)

            QMessageBox.information(self, "Selection", "All visible files have been selected.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to select files: {str(e)}")

    def delete_selected_files(self):
        """Delete all selected files with confirmation."""
        selected_indexes = self.downloaded_tree.selectionModel().selectedIndexes()
        unique_indexes = set()
        file_paths = []

        for index in selected_indexes:
            if index.column() == 0:
                unique_indexes.add(index)
                file_path = self.downloaded_model.filePath(index)
                file_paths.append(file_path)

        if not file_paths:
            QMessageBox.warning(self, "No Selection", "No files selected for deletion.")
            return

        confirmation = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete {len(file_paths)} file(s)?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirmation == QMessageBox.Yes:
            success_count = 0
            failed_files = []

            for file_path in file_paths:
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                    success_count += 1
                except Exception as e:
                    failed_files.append(f"{os.path.basename(file_path)}: {str(e)}")

            self.refresh_file_tree()

            if failed_files:
                error_msg = "\n".join(failed_files)
                QMessageBox.warning(
                    self,
                    "Deletion Results",
                    f"Successfully deleted {success_count} file(s).\n\nFailed to delete {len(failed_files)} file(s):\n{error_msg}"
                )
            else:
                QMessageBox.information(
                    self,
                    "Deletion Complete",
                    f"Successfully deleted {success_count} file(s)."
                )
                
    def remove_empty_folders(self):
        """Remove all empty folders in the download directory."""
        try:
            root_path = str(self.download_dir)
            deleted_count = 0

            for root, dirs, files in os.walk(root_path, topdown=False):  # Topdown=False ensures we process leaves first
                for dir in dirs:
                    dir_path = os.path.join(root, dir)
                    try:
                        if not os.listdir(dir_path):  # Check if the directory is empty
                            os.rmdir(dir_path)
                            deleted_count += 1
                            print(f"Removed empty folder: {dir_path}") # Debug print
                    except OSError as e:
                        print(f"Error removing folder {dir_path}: {e}")  # Handle potential errors

            QMessageBox.information(self, "Empty Folders Removed", f"Successfully removed {deleted_count} empty folders.")
            self.refresh_file_tree() # Refresh the tree view after deleting folders

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to remove empty folders: {str(e)}")

    def show_context_menu(self, position):
        """Show context menu for tree view items."""
        context_menu = QMenu()
        index = self.downloaded_tree.indexAt(position)
        
        if index.isValid():
            file_path = self.downloaded_model.filePath(index)
            
            # Add menu items
            open_action = context_menu.addAction("Open")
            
            # Add PyMuPDF options only for files (not directories)
            if os.path.isfile(file_path):
                open_pymupdf_action = context_menu.addAction("Open With PyMuPDF")
                extract_text_action = context_menu.addAction("Open File With Extracted Text")
            
            delete_action = context_menu.addAction("Delete File")
            
            # Show menu and handle actions
            action = context_menu.exec_(self.downloaded_tree.viewport().mapToGlobal(position))
            
            if action == open_action:
                self.open_downloaded_file(index)
            elif action == delete_action:
                if len(self.downloaded_tree.selectionModel().selectedIndexes()) <= 1:
                    self.downloaded_tree.selectionModel().select(index, QItemSelectionModel.ClearAndSelect)
                self.delete_selected_files()
            elif os.path.isfile(file_path) and action == open_pymupdf_action:
                self.open_file_with_pymupdf(file_path)
            elif os.path.isfile(file_path) and action == extract_text_action:
                self.extract_text_from_file(file_path)

    def open_downloaded_file(self, index):
        """Open the selected downloaded file with its default application."""
        file_path = self.downloaded_model.filePath(index)
        if os.path.isfile(file_path):
            try:
                QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open file: {str(e)}")

    def show_text(self, data: bytes, filename: str):
        """Display text content in a scrollable editor with improved formatting and search functionality."""
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError as e:
            logger.error(f"Failed to decode text content: {e}")
            text = "Unable to decode text content."

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Text Preview: {filename}")
        layout = QVBoxLayout(dlg)
        
        # Add integrated search bar (initially hidden)
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        
        search_field = QLineEdit()
        search_field.setPlaceholderText("Search text...")
        search_layout.addWidget(search_field)
        
        case_sensitive = QCheckBox("Case sensitive")
        search_layout.addWidget(case_sensitive)
        
        whole_words = QCheckBox("Whole words")
        search_layout.addWidget(whole_words)
        
        prev_btn = QPushButton("Previous")
        search_layout.addWidget(prev_btn)
        
        next_btn = QPushButton("Next")
        search_layout.addWidget(next_btn)
        
        close_search_btn = QPushButton("×")
        close_search_btn.setFixedSize(25, 25)
        close_search_btn.setToolTip("Close search")
        search_layout.addWidget(close_search_btn)
        
        search_container.setVisible(False)
        layout.addWidget(search_container)
        
        # Create text editor
        editor = QTextEdit()
        editor.setPlainText(text)
        editor.setReadOnly(True)
        editor.setLineWrapMode(QTextEdit.NoWrap)
        editor.setStyleSheet("""
            QTextEdit {
                font-family: monospace;
                font-size: 12pt;
            }
        """)
        
        # Add widgets to layout
        layout.addWidget(editor)
        
        # Button container
        btn_layout = QHBoxLayout()
        
        # Fullscreen button
        btn_fullscreen = QPushButton("Full Screen (F11)")
        btn_fullscreen.clicked.connect(lambda: self.toggle_fullscreen(dlg, btn_fullscreen))
        
        # Close button
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dlg.accept)
        
        btn_layout.addWidget(btn_fullscreen)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        
        # Configure dialog dimensions
        dlg.resize(800, 600)
        dlg.setMinimumSize(400, 300)
        
        # Add keyboard shortcut for F11
        QShortcut(Qt.Key_F11, dlg).activated.connect(
            lambda: self.toggle_fullscreen(dlg, btn_fullscreen)
        )
        
        # Function to toggle search bar visibility
        def toggle_search_bar():
            search_container.setVisible(not search_container.isVisible())
            if search_container.isVisible():
                search_field.setFocus()
                search_field.selectAll()
        
        # Function to handle search
        def find_text(direction=1):
            search_text = search_field.text()
            if not search_text:
                return
            
            # Set search options
            flags = QTextDocument.FindFlags()
            if case_sensitive.isChecked():
                flags |= QTextDocument.FindCaseSensitively
            if whole_words.isChecked():
                flags |= QTextDocument.FindWholeWords
            if direction < 0:
                flags |= QTextDocument.FindBackward
            
            # Perform search
            cursor = editor.textCursor()
            # If searching backwards, we need to move cursor to selection start
            if direction < 0 and cursor.hasSelection():
                position = cursor.selectionStart()
                cursor.setPosition(position)
                editor.setTextCursor(cursor)
                
            found = editor.find(search_text, flags)
            
            # If not found, try wrapping around
            if not found:
                # Save current cursor
                temp_cursor = editor.textCursor()
                # Move to beginning/end based on direction
                cursor = editor.textCursor()
                if direction > 0:
                    cursor.movePosition(QTextCursor.Start)
                else:
                    cursor.movePosition(QTextCursor.End)
                editor.setTextCursor(cursor)
                
                # Try search again
                found = editor.find(search_text, flags)
                
                # If still not found, restore original cursor
                if not found:
                    editor.setTextCursor(temp_cursor)
                    QMessageBox.information(dlg, "Search Result", f"No matches found for '{search_text}'")
        
        # Search connections
        shortcut_find = QShortcut(QKeySequence("Ctrl+F"), dlg)
        shortcut_find.activated.connect(toggle_search_bar)
        
        close_search_btn.clicked.connect(toggle_search_bar)
        
        search_field.returnPressed.connect(lambda: find_text(1))
        next_btn.clicked.connect(lambda: find_text(1))
        prev_btn.clicked.connect(lambda: find_text(-1))
        
        # Additional keyboard shortcuts for search
        shortcut_find_next = QShortcut(QKeySequence("F3"), dlg)
        shortcut_find_next.activated.connect(lambda: find_text(1))
        
        shortcut_find_prev = QShortcut(QKeySequence("Shift+F3"), dlg)
        shortcut_find_prev.activated.connect(lambda: find_text(-1))
        
        shortcut_close_search = QShortcut(QKeySequence("Escape"), dlg)
        shortcut_close_search.activated.connect(lambda: 
            search_container.setVisible(False) if search_container.isVisible() else None
        )
        
        dlg.exec_()

    def toggle_fullscreen(self, dialog, button):
        if dialog.isFullScreen():
            dialog.showNormal()
            button.setText("Full Screen (F11)")
        else:
            dialog.showFullScreen()
            button.setText("Exit Full Screen (F11)")
        
    def open_file_with_pymupdf(self, file_path):
        """
        Open a file using PyMuPDF and display its pages as images.
        
        Args:
            file_path (str): Path to the file to open
        """
        try:
            # Determine file extension to handle files with incorrect extensions
            file_ext = os.path.splitext(file_path)[1].lower()
            filetype = None
            
            # Handle special cases for file extensions
            if file_ext not in ['.pdf', '.xps', '.epub', '.mobi', '.fb2', '.cbz', '.svg', '.txt',
                               '.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.pnm', '.pgm', 
                               '.pbm', '.ppm', '.pam', '.jxr', '.jpx', '.jp2', '.psd']:
                # Try to determine file type based on content (default to PDF)
                if any(file_path.lower().endswith(ext) for ext in ['.txt', '.py', '.json', '.xml', '.html', '.htm']):
                    filetype = "txt"
            
            # Call the paginated document viewer
            self.show_paginated_document(os.path.basename(file_path), file_path, filetype)
            
        except Exception as e:
            logger.error(f"Failed to open file with PyMuPDF: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to open file with PyMuPDF: {str(e)}")
            
    def show_paginated_document(self, filename: str, file_path, filetype: str = None):
        """Display a paginated document with navigation and zoom controls."""
        try:
            doc_dialog = QDialog(self)
            doc_dialog.setWindowTitle(f"Document Preview: {filename}")
            layout = QVBoxLayout(doc_dialog)

            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            image_label = QLabel()
            image_label.setAlignment(Qt.AlignCenter)
            scroll_area.setWidget(image_label)
            layout.addWidget(scroll_area)

            nav_layout = QHBoxLayout()
            nav_layout.addWidget(QLabel("Page:"))
            page_input = QLineEdit()
            page_input.setMaximumWidth(50)
            nav_layout.addWidget(page_input)
            page_label = QLabel("")
            nav_layout.addWidget(page_label)
            btn_go = QPushButton("Go")
            nav_layout.addWidget(btn_go)
            
            # Add fullscreen button next to Go button
            btn_fullscreen = QPushButton("Full Screen (F11)")
            btn_fullscreen.setToolTip("Toggle fullscreen mode (F11)")
            nav_layout.addWidget(btn_fullscreen)
            
            nav_layout.addStretch()
            btn_prev = QPushButton("◀ Previous")
            btn_next = QPushButton("Next ▶")
            nav_layout.addWidget(btn_prev)
            nav_layout.addWidget(btn_next)
            layout.addLayout(nav_layout)

            zoom_layout = QHBoxLayout()
            zoom_out = QPushButton("Zoom Out")
            zoom_reset = QPushButton("Reset Zoom")
            zoom_in = QPushButton("Zoom In")
            zoom_layout.addWidget(zoom_out)
            zoom_layout.addWidget(zoom_reset)
            zoom_layout.addWidget(zoom_in)
            layout.addLayout(zoom_layout)

            # Fullscreen state tracking
            previous_size = None
            is_fullscreen = False

            def toggle_fullscreen():
                """Toggle between fullscreen and normal window mode."""
                nonlocal previous_size, is_fullscreen
                if is_fullscreen:
                    # Restore normal mode
                    doc_dialog.showNormal()
                    btn_fullscreen.setText("Full Screen (F11)")
                    if previous_size:
                        doc_dialog.resize(previous_size)
                else:
                    # Enter fullscreen mode
                    previous_size = doc_dialog.size()
                    doc_dialog.showFullScreen()
                    btn_fullscreen.setText("Exit Full Screen (F11)")
                is_fullscreen = not is_fullscreen

            # Set up F11 shortcut
            fullscreen_shortcut = QShortcut(QKeySequence("F11"), doc_dialog)
            fullscreen_shortcut.activated.connect(toggle_fullscreen)
            btn_fullscreen.clicked.connect(toggle_fullscreen)

            current_page = 0
            self.doc_renderer = DocumentRenderer()

            def update_document_ui(dialog, label, input_field, page_lbl, prev_btn, next_btn, 
                                  pixmap, page_num, total_pages, doc_name):
                """Update the UI with the rendered page and navigation state."""
                label.setPixmap(pixmap)
                input_field.setText(str(page_num + 1))
                page_lbl.setText(f" of {total_pages}")
                prev_btn.setEnabled(page_num > 0)
                next_btn.setEnabled(page_num < total_pages - 1)
                dialog.setWindowTitle(f"Document Preview: {doc_name} - Page {page_num + 1}")

            self.doc_renderer.page_rendered.connect(
                lambda pixmap, page_num, total_pages: update_document_ui(
                    doc_dialog, image_label, page_input, page_label, btn_prev, btn_next,
                    pixmap, page_num, total_pages, filename
                )
            )
            self.doc_renderer.render_error.connect(lambda msg: QMessageBox.critical(doc_dialog, "Error", msg))

            if not self.doc_renderer.load_document(file_path, filetype):
                doc_dialog.close()
                return

            def on_prev():
                nonlocal current_page
                if current_page > 0:
                    current_page -= 1
                    self.doc_renderer.render_page(current_page)

            def on_next():
                nonlocal current_page
                if current_page < self.doc_renderer.doc.page_count - 1:
                    current_page += 1
                    self.doc_renderer.render_page(current_page)

            def on_go():
                nonlocal current_page
                try:
                    page_num = int(page_input.text()) - 1
                    if 0 <= page_num < self.doc_renderer.doc.page_count:
                        current_page = page_num
                        self.doc_renderer.render_page(current_page)
                    else:
                        QMessageBox.warning(doc_dialog, "Warning", f"Page number must be between 1 and {self.doc_renderer.doc.page_count}")
                except ValueError:
                    QMessageBox.warning(doc_dialog, "Warning", "Please enter a valid page number")

            def on_zoom_change(new_zoom):
                self.doc_renderer.set_zoom(new_zoom)
                # After changing zoom, re-render the current page
                self.doc_renderer.render_page(current_page)

            btn_prev.clicked.connect(on_prev)
            btn_next.clicked.connect(on_next)
            btn_go.clicked.connect(on_go)
            page_input.returnPressed.connect(on_go)
            zoom_in.clicked.connect(lambda: on_zoom_change(self.doc_renderer.zoom_level * 1.25))
            zoom_out.clicked.connect(lambda: on_zoom_change(self.doc_renderer.zoom_level * 0.8))
            zoom_reset.clicked.connect(lambda: on_zoom_change(1.5))

            def close_document_renderer():
                """Clean up the document renderer resources."""
                if hasattr(self, 'doc_renderer') and self.doc_renderer:
                    self.doc_renderer.close()
                    self.doc_renderer = None

            doc_dialog.finished.connect(close_document_renderer)
            self.doc_renderer.render_page(0)

            # Set initial window size
            doc_dialog.resize(800, 800)
            doc_dialog.exec_()

        except Exception as e:
            logger.error(f"Error opening document {filename}: {e}")
            QMessageBox.critical(self, "Error", f"Error opening document: {e}")
            self.close_document_renderer()

    def close_document_renderer(self):
        """Closes the document renderer and releases resources."""
        if hasattr(self, 'doc_renderer') and self.doc_renderer:
            self.doc_renderer.close()
            self.doc_renderer = None

    def extract_text_from_file(self, file_path):
        """
        Extract text from a file using PyMuPDF and display it in a dialog.
        
        Args:
            file_path (str): Path to the file to extract text from
        """
        try:
            # Determine file extension to handle files with incorrect extensions
            file_ext = os.path.splitext(file_path)[1].lower()
            filetype = None
            
            # Handle special cases for file extensions
            if file_ext not in ['.pdf', '.xps', '.epub', '.mobi', '.fb2', '.cbz', '.svg', '.txt',
                              '.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.pnm', '.pgm', 
                              '.pbm', '.ppm', '.pam', '.jxr', '.jpx', '.jp2', '.psd']:
                # Try to determine file type based on content (default to PDF)
                if any(file_path.lower().endswith(ext) for ext in ['.txt', '.py', '.json', '.xml', '.html', '.htm']):
                    filetype = "txt"
            
            # Open the document with PyMuPDF
            doc = fitz.open(file_path, filetype=filetype)
            
            # Extract text from all pages
            all_text = ""
            for page_num in range(doc.page_count):
                page = doc[page_num]
                all_text += f"--- Page {page_num + 1} ---\n"
                all_text += page.get_text()
                all_text += "\n\n"
            
            # Create a dialog to display the extracted text
            with doc:  # Use context manager to ensure doc is closed
                self.show_text(all_text.encode('utf-8'), os.path.basename(file_path))
            
        except Exception as e:
            logger.error(f"Failed to extract text from file: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to extract text from file: {str(e)}")