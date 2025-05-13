from PyQt5.QtWidgets import QDialog, QVBoxLayout, QScrollArea, QWidget, QLabel, QHBoxLayout, QLineEdit, QPushButton, QComboBox, QListView, QProgressBar, QProgressDialog, QMessageBox, QTextEdit, QSizePolicy, QAbstractItemView, QMenu, QSlider, QShortcut
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSortFilterProxyModel, QObject, QUrl, QPoint, QMutex
from PyQt5.QtGui import QPixmap, QImage, QStandardItemModel, QStandardItem, QDesktopServices, QKeySequence
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from internetarchive import get_item, download
import logging
import time
from pathlib import Path
from typing import List
from PIL import Image
from io import BytesIO
import pymupdf as fitz

# Configure logging to track application events and errors
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("archive_viewer.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ArchiveViewer")

class DownloadWorker(QThread):
    """Worker thread for downloading files asynchronously."""
    progress_signal = pyqtSignal(int, int)  # Signal for download progress
    finished_signal = pyqtSignal(bool, str)  # Signal for download completion

    def __init__(self, identifier: str, files: List[str], session, dest_dir: Path):
        super().__init__()
        self.identifier = identifier
        self.files = files
        self.session = session
        self.dest_dir = dest_dir
        self.is_cancelled = False

    def run(self):
        total_files = len(self.files)
        failed = []

        for i, file in enumerate(self.files):
            if self.is_cancelled:
                self.finished_signal.emit(False, "Download cancelled by user")
                return

            self.progress_signal.emit(i, total_files)
            try:
                download(
                    self.identifier,
                    files=[file],
                    verbose=False,
                    archive_session=self.session,
                    destdir=str(self.dest_dir)
                )
                self.progress_signal.emit(i + 1, total_files)
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error downloading file {file}: {e}")
                failed.append((file, str(e)))
                # Continue with next file instead of aborting
                continue

        if failed:
            failed_list = ", ".join(f for f, unused in failed)
            self.finished_signal.emit(False, f"Some files failed to download: {failed_list}")
        else:
            self.finished_signal.emit(True, "All files downloaded successfully")

    def cancel(self):
        """Cancel the ongoing download operation."""
        self.is_cancelled = True

class FileLoadWorker(QThread):
    """Worker thread for loading file content asynchronously."""
    finished_signal = pyqtSignal(object, str, str)  # Signal for file load completion

    def __init__(self, item, filename: str):
        super().__init__()
        self.item = item
        self.filename = filename

    def run(self):
        """Load file content in a separate thread."""
        try:
            file_obj = self.item.get_file(self.filename)
            resp = file_obj.download(return_responses=True)
            self.finished_signal.emit(resp.content, self.filename, "")
        except Exception as e:
            logger.error(f"Failed to fetch file {self.filename}: {e}")
            self.finished_signal.emit(None, self.filename, str(e))


class PageRenderer(QThread):
    """Worker thread for rendering document pages asynchronously."""
    page_rendered = pyqtSignal(QPixmap, int)  # Signal when a page is rendered
    render_error = pyqtSignal(str, int)  # Signal for rendering errors

    def __init__(self, doc, zoom_level):
        super().__init__()
        self.doc = doc
        self.zoom_level = zoom_level
        self.page_queue = []  # Queue of pages to render
        self.mutex = QMutex()  # To protect the queue from concurrent access
        self.running = True

    def run(self):
        """Process the page rendering queue."""
        while self.running:
            page_num = None
            self.mutex.lock()
            if self.page_queue:
                page_num = self.page_queue.pop(0)
            self.mutex.unlock()
            
            if page_num is not None:
                try:
                    page = self.doc.load_page(page_num)
                    matrix = fitz.Matrix(self.zoom_level, self.zoom_level)
                    pix = page.get_pixmap(matrix=matrix, alpha=False)
                    img = QImage(
                        pix.samples,
                        pix.width,
                        pix.height,
                        pix.stride,
                        QImage.Format_RGB888
                    )
                    pixmap = QPixmap.fromImage(img)
                    self.page_rendered.emit(pixmap, page_num)
                except Exception as e:
                    self.render_error.emit(str(e), page_num)
            else:
                # Sleep a bit to avoid high CPU usage when the queue is empty
                self.msleep(100)

    def render_page(self, page_num):
        """Add a page to the rendering queue and start the thread if not running."""
        self.mutex.lock()
        if page_num not in self.page_queue:
            self.page_queue.append(page_num)
        self.mutex.unlock()
        
        if not self.isRunning():
            self.start()
    
    def stop(self):
        """Stop the rendering thread safely."""
        self.running = False
        self.wait()  # Wait for the thread to finish

    def update_zoom_level(self, zoom_level):
        """Update the zoom level used for rendering."""
        self.zoom_level = zoom_level

class DocumentRenderer(QObject):
    """Handles rendering of document pages with caching and zoom functionality."""
    page_rendered = pyqtSignal(QPixmap, int, int)  # Signal for rendered page
    render_error = pyqtSignal(str)  # Signal for general rendering errors

    def __init__(self):
        super().__init__()
        self.doc = None
        self.zoom_level = 1.5
        self.page_cache = {}
        self.MAX_CACHE_SIZE = 5
        self.renderer_thread = None  # Reference to the rendering thread

    def load_document(self, data, filetype):
        """Load a document from binary data."""
        try:
            self.doc = fitz.open(stream=data, filetype=filetype)
            if self.doc.page_count == 0:
                self.render_error.emit("Document contains no pages")
                return False
            return True
        except Exception as e:
            self.render_error.emit(f"Error opening document: {str(e)}")
            return False

    def render_page(self, page_num):
        """Render a specific page of the document asynchronously."""
        if not self.doc or page_num < 0 or page_num >= self.doc.page_count:
            return

        # Check if the page is already in the cache at the current zoom level
        cache_key = (page_num, self.zoom_level)
        if cache_key in self.page_cache:
            self.page_rendered.emit(self.page_cache[cache_key], page_num, self.doc.page_count)
            return

        if not self.renderer_thread:
            self.renderer_thread = PageRenderer(self.doc, self.zoom_level)
            self.renderer_thread.page_rendered.connect(self.on_page_rendered)
            self.renderer_thread.render_error.connect(self.on_render_error)

        self.renderer_thread.render_page(page_num)

    def on_page_rendered(self, pixmap, page_num):
        """Handle a successfully rendered page."""
        cache_key = (page_num, self.zoom_level)
        self.page_cache[cache_key] = pixmap
        
        # Manage cache size
        if len(self.page_cache) > self.MAX_CACHE_SIZE:
            oldest_key = list(self.page_cache.keys())[0]  # Get the first inserted key
            del self.page_cache[oldest_key]
            
        self.page_rendered.emit(pixmap, page_num, self.doc.page_count)

    def on_render_error(self, error_msg, page_num):
        """Handle rendering errors for individual pages."""
        logger.error(f"Error rendering page {page_num}: {error_msg}")
        self.render_error.emit(f"Error rendering page {page_num+1}: {error_msg}")

    def set_zoom(self, zoom_level):
        """Adjust the zoom level and clear the cache if changed."""
        if zoom_level != self.zoom_level:
            self.zoom_level = zoom_level
            # Clear cache for pages at the old zoom level
            self.page_cache.clear()
            
            # Update zoom level in the renderer thread if it exists
            if self.renderer_thread:
                # Stop the current thread and create a new one with the updated zoom level
                self.renderer_thread.stop()
                self.renderer_thread = PageRenderer(self.doc, self.zoom_level)
                self.renderer_thread.page_rendered.connect(self.on_page_rendered)
                self.renderer_thread.render_error.connect(self.on_render_error)

    def close(self):
        """Clean up resources when done."""
        if self.doc:
            self.doc.close()
            self.doc = None
        if self.renderer_thread:
            self.renderer_thread.stop()
            self.renderer_thread = None

class ProgressDialog(QProgressDialog):
    """Custom progress dialog for showing ongoing operations."""
    def __init__(self, title, message, cancel_button_text, parent=None):
        super().__init__(message, cancel_button_text, 0, 0, parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModal)
        self.setMinimumDuration(0)
        self.setCancelButton(None)
        self.setAutoClose(False)
        self.setAutoReset(False)
        self.setMinimumWidth(400)
        self.setStyleSheet("""
            QProgressDialog { background-color: #f5f5f5; border: 1px solid #dcdcdc; border-radius: 5px; }
            QLabel { font-size: 12px; color: #333333; }
            QPushButton { background-color: #e74c3c; color: white; border: none; border-radius: 3px; padding: 5px 15px; }
            QPushButton:hover { background-color: #c0392b; }
        """)
        self.cancel_btn = QPushButton(cancel_button_text)
        self.setCancelButton(self.cancel_btn)

class ItemDetailsDialog(QDialog):
    """Dialog to display item details and manage file operations."""
    def __init__(self, identifier: str, session, download_dir: Path):
        super().__init__()
        self.setWindowTitle(f"Item Details: {identifier}")
        self.setGeometry(200, 200, 800, 600)
        self.session = session
        self.identifier = identifier
        self.download_dir = download_dir
        self.download_worker = None
        self.file_load_worker = None
        self.doc_renderer = None
        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog's user interface."""
        layout = QVBoxLayout(self)

        try:
            logger.info(f"Fetching item details for {self.identifier}")
            self.item = get_item(identifier=self.identifier, archive_session=self.session)
            metadata = self.item.item_metadata.get('metadata', {})
        except Exception as e:
            error_msg = f"Failed to fetch item details: {e}"
            logger.error(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
            self.close()
            return

        title = metadata.get('title', 'No title')
        desc = metadata.get('description', 'No description')

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        lbl_title = QLabel(f"<b>Title:</b> {title}")
        lbl_title.setWordWrap(True)
        lbl_title.setTextInteractionFlags(Qt.TextSelectableByMouse)

        lbl_desc = QLabel(f"<b>Description:</b> {desc}")
        lbl_desc.setWordWrap(True)
        lbl_desc.setTextInteractionFlags(Qt.TextSelectableByMouse)

        content_layout.addWidget(lbl_title)
        content_layout.addWidget(lbl_desc)
        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area, 1)

        files_section = QVBoxLayout()
        files_section.addWidget(QLabel("<b>Files:</b>"))

        files_header = QHBoxLayout()
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Filter:"))
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Enter file name to filter...")
        self.search_field.textChanged.connect(self.filter_files)
        search_layout.addWidget(self.search_field)
        files_header.addLayout(search_layout)

        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["All Files", "Images", "Ebooks", "Documents", "Audio", "Video", "Archive", "Other"])
        self.type_combo.currentIndexChanged.connect(self.filter_files)
        type_layout.addWidget(self.type_combo)
        files_header.addLayout(type_layout)

        sort_layout = QHBoxLayout()
        sort_layout.addWidget(QLabel("Sort by:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Name (A-Z)", "Name (Z-A)", "Size (Small-Large)", "Size (Large-Small)"])
        self.sort_combo.currentIndexChanged.connect(self.sort_files)
        sort_layout.addWidget(self.sort_combo)
        files_header.addLayout(sort_layout)

        files_section.addLayout(files_header)

        self.files_model = QStandardItemModel()
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.files_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self.files_list = QListView()
        self.files_list.setModel(self.proxy_model)
        self.files_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.files_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.files_list.customContextMenuRequested.connect(self.show_context_menu)
        self.files_list.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.files_data = []

        try:
            for file_info in self.item.files:
                item = QStandardItem(file_info['name'])
                item.setCheckable(True)
                item.setCheckState(Qt.Unchecked)
                item.setData(file_info.get('size', 0), Qt.UserRole)
                self.files_model.appendRow(item)
                self.files_data.append({
                    'name': file_info['name'],
                    'size': int(file_info.get('size', 0)),
                    'item': item
                })
        except Exception as e:
            logger.error(f"Error loading file list: {e}")
            QMessageBox.warning(self, "Warning", f"Error loading file list: {e}")

        files_section.addWidget(self.files_list, 3)

        dl_controls = QHBoxLayout()
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.clicked.connect(self.select_all_files)
        dl_controls.addWidget(self.btn_select_all)

        self.btn_select_none = QPushButton("Select None")
        self.btn_select_none.clicked.connect(self.select_no_files)
        dl_controls.addWidget(self.btn_select_none)

        self.btn_download = QPushButton("Download Selected Files")
        self.btn_download.clicked.connect(self.download_selected_files)
        dl_controls.addWidget(self.btn_download)

        files_section.addLayout(dl_controls)
        layout.addLayout(files_section, 2)

    def show_context_menu(self, position: QPoint):
        """Display a context menu for selected files."""
        indexes = self.files_list.selectedIndexes()
        if not indexes:
            return

        menu = QMenu()
        open_action = menu.addAction("Open File")
        action = menu.exec_(self.files_list.viewport().mapToGlobal(position))

        if action == open_action:
            for index in indexes:
                source_index = self.proxy_model.mapToSource(index)
                item = self.files_model.itemFromIndex(source_index)
                self.open_file(item.text())

    def filter_files(self):
        """Filter the file list based on search text and type."""
        search_text = self.search_field.text()
        selected_type = self.type_combo.currentText()
        model = self.proxy_model.sourceModel()
        model.clear()
        
        # Filter files based on search text and type
        self.filtered_files_data = []
        for file_data in self.files_data:
            name = file_data['name']
            ext = Path(name).suffix.lower().lstrip('.')
            if selected_type == "All Files" or (
                selected_type == "Images" and ext in {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'svg', 'webp', 'ico', 'heic', 'raw'} or
                selected_type == "Ebooks" and ext in {'epub', 'mobi', 'fb2', 'pdf', 'xps'} or
                selected_type == "Documents" and ext in {'txt', 'md', 'tex', 'doc', 'docx', 'odt', 'rtf'} or
                selected_type == "Audio" and ext in {'mp3', 'wav', 'ogg', 'flac', 'aac', 'wma', 'm4a', 'opus'} or
                selected_type == "Video" and ext in {'mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm', 'mpeg', 'mpg'} or
                selected_type == "Archive" and ext in {'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'iso', 'xz'} or
                selected_type == "Other" and ext in {'sqlite', 'torrent', 'csv', 'xml', 'json', 'html', 'htm'}
            ):
                if search_text.lower() in name.lower():
                    # Add file to filtered list if it matches criteria
                    self.filtered_files_data.append(file_data)
        
        # Update the model with filtered data
        self.update_model_from_filtered_data()
        
        # Apply current sort after filtering
        self.sort_files(preserve_filter=True)
        
    def sort_files(self, preserve_filter=False):
        """
        Sort the file list based on the selected option.
        
        Args:
            preserve_filter (bool): If True, sort only the filtered files
                                   If False, sort all files and reapply filter
        """
        sort_index = self.sort_combo.currentIndex()
        
        # Use the appropriate data source based on preserve_filter
        source_data = self.filtered_files_data if preserve_filter else self.files_data
        
        if sort_index == 0:  # A-Z
            source_data.sort(key=lambda x: x['name'].lower())
        elif sort_index == 1:  # Z-A
            source_data.sort(key=lambda x: x['name'].lower(), reverse=True)
        elif sort_index == 2:  # Size ascending
            source_data.sort(key=lambda x: x['size'])
        elif sort_index == 3:  # Size descending
            source_data.sort(key=lambda x: x['size'], reverse=True)
        
        # If we're not preserving the filter, we need to refilter after sorting
        if not preserve_filter:
            self.filter_files()
        else:
            # Just update the model with the sorted filtered data
            self.update_model_from_filtered_data()

    def reorder_items(self):
        """Reorder items in the model based on sorted files_data."""
        check_states = {self.files_model.item(i).text(): self.files_model.item(i).checkState() for i in range(self.files_model.rowCount())}
        self.files_model.clear()
        for file_data in self.files_data:
            item = QStandardItem(file_data['name'])
            item.setCheckable(True)
            item.setCheckState(check_states.get(file_data['name'], Qt.Unchecked))
            item.setData(file_data['size'], Qt.UserRole)
            self.files_model.appendRow(item)
            
    def update_model_from_filtered_data(self):
        """Update the model using the current filtered_files_data."""
        # Save current check states
        model = self.proxy_model.sourceModel()
        check_states = {model.item(i).text(): model.item(i).checkState() 
                        for i in range(model.rowCount())} if model.rowCount() > 0 else {}
        
        # Clear and rebuild model
        model.clear()
        
        for file_data in self.filtered_files_data:
            item = QStandardItem(file_data['name'])
            item.setCheckable(True)
            item.setCheckState(check_states.get(file_data['name'], Qt.Unchecked))
            item.setData(file_data['size'], Qt.UserRole)
            model.appendRow(item)

    def select_all_files(self):
        """Check all files in the list."""
        for i in range(self.files_model.rowCount()):
            self.files_model.item(i).setCheckState(Qt.Checked)

    def select_no_files(self):
        """Uncheck all files in the list."""
        for i in range(self.files_model.rowCount()):
            self.files_model.item(i).setCheckState(Qt.Unchecked)

    def download_selected_files(self):
        """Initiate download of selected files."""
        selected = [self.files_model.item(i).text() for i in range(self.files_model.rowCount()) if self.files_model.item(i).checkState() == Qt.Checked]
        if not selected:
            QMessageBox.warning(self, "Warning", "No files selected for download")
            return

        self.progress_dialog = ProgressDialog("Downloading", f"Starting download of {len(selected)} items...", "Cancel", self)
        self.progress_dialog.canceled.connect(self.cancel_download)
        self.progress_dialog.show()
        self.btn_download.setEnabled(False)

        try:
            self.download_worker = DownloadWorker(self.identifier, selected, self.session, self.download_dir)
            self.download_worker.progress_signal.connect(self.update_progress)
            self.download_worker.finished_signal.connect(self.download_finished)
            self.download_worker.start()
        except Exception as e:
            logger.error(f"Failed to start download: {e}")
            QMessageBox.critical(self, "Error", f"Failed to start download: {e}")
            self.reset_download_ui()

    def update_progress(self, current: int, total: int):
        """Update the progress dialog during download."""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.setLabelText(f"Downloading {current} of {total} files...")

    def download_finished(self, success: bool, message: str):
        """Handle the completion of the download process."""
        self.reset_download_ui()
        if success:
            logger.info(f"Download completed successfully: {message}")
            QMessageBox.information(self, "Success", message)
        else:
            logger.error(f"Download failed: {message}")
            QMessageBox.critical(self, "Error", message)

    def reset_download_ui(self):
        """Reset UI elements after download."""
        self.btn_download.setEnabled(True)
        self.download_worker = None
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

    def cancel_download(self):
        """Cancel the current download operation."""
        if self.download_worker and self.download_worker.isRunning():
            logger.info("Cancelling download")
            self.download_worker.cancel()
            self.reset_download_ui()

    def open_file(self, filename: str):
        """Open and preview a file based on its type."""
        logger.info(f"Opening file: {filename}")
        ext = Path(filename).suffix.lower().lstrip('.')

        try:
            # Verify file is part of the item's files
            if not any(f['name'] == filename for f in self.item.files):
                raise FileNotFoundError(f"File {filename} not found in the item.")

            # Define supported extensions
            image_exts = {
                'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff',
                'pnm', 'pgm', 'pbm', 'ppm', 'pam', 'jxr', 'jpx', 'jp2', 'psd'
            }
            audio_exts = {
                'mp3',   # MPEG Audio Layer III
                'wav',   # PCM/RIFF
                'ogg',   # Ogg Vorbis
                'flac',  # Free Lossless Audio Codec
                'aac',   # Advanced Audio Coding
                'm4a',   # MPEG‑4 Audio container
                'wma',   # Windows Media Audio
                'aif',   # AIFF uncompressed
                'aiff',
                'mid',   # MIDI
                'midi',
                'mp2',   # MPEG Audio Layer II
                'mpga',  # MPEG Audio container
                'opus'   # Opus codec in Ogg
            }
            text_exts = {
                'txt',   # plain text
                'xml',   # Extensible Markup Language
                'json',  # JavaScript Object Notation
                'csv',   # Comma-Separated Values
                'html',  # HyperText Markup Language
                'htm',   # HTML variant
                'py',    # Python source
                'cs',    # C# source
                'md',    # Markdown
                'yaml',  # YAML Ain't Markup Language
                'yml',   # YAML variant
                'ini',   # INI configuration
                'log'    # log files
            }
            doc_exts = {
                'pdf', 'xps', 'epub', 'mobi', 'fb2', 'cbz', 'svg', 'txt'
            }

            if ext in image_exts:
                # Load and display image
                self.load_file_content(filename, self.show_image)

            elif ext in audio_exts:
                # Play audio files
                file_obj = self.item.get_file(filename)
                self.play_audio(file_obj)

            elif ext in text_exts:
                # Load and display plain text or code
                self.load_file_content(filename, self.show_text)

            elif ext in doc_exts:
                # Load and display paginated document formats
                self.load_file_content(
                    filename,
                    lambda data, name: self.show_paginated_document(name, data, ext)
                )

            else:
                # Fallback: open via external URL
                file_url = QUrl(f"https://archive.org/download/{self.identifier}/{filename}")
                QDesktopServices.openUrl(file_url)

        except Exception as e:
            logger.error(f"Failed to open file: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open file: {e}")

    def load_file_content(self, filename: str, callback_func):
        """Load file content asynchronously and call the callback function."""
        loading_dialog = QDialog(self)
        loading_dialog.setWindowTitle("Loading File")
        loading_layout = QVBoxLayout(loading_dialog)
        loading_layout.addWidget(QLabel(f"Loading {filename}..."))
        loading_progress = QProgressBar()
        loading_progress.setRange(0, 0)
        loading_layout.addWidget(loading_progress)

        self.file_load_worker = FileLoadWorker(self.item, filename)

        def on_file_loaded(data, name, error):
            loading_dialog.close()
            if error:
                QMessageBox.critical(self, "Error", f"Failed to load file: {error}")
            elif data:
                callback_func(data, name)

        self.file_load_worker.finished_signal.connect(on_file_loaded)
        self.file_load_worker.start()
        loading_dialog.exec_()

    def show_image(self, data: bytes, filename: str):
        """Display an image with zoom controls."""
        try:
            image = QImage.fromData(data)
            if image.isNull():
                logger.error(f"Failed to load image from data: {filename}")
                QMessageBox.critical(self, "Error", "Failed to load image data.")
                return

            pixmap = QPixmap.fromImage(image)
            preview_dialog = QDialog(self)
            preview_dialog.setWindowTitle(f"Image Preview: {filename}")
            layout = QVBoxLayout(preview_dialog)

            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            image_label = QLabel()
            image_label.setAlignment(Qt.AlignCenter)
            image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
            scroll_area.setWidget(image_label)
            layout.addWidget(scroll_area)

            zoom_layout = QHBoxLayout()
            zoom_out = QPushButton("Zoom Out")
            zoom_reset = QPushButton("Reset Zoom")
            zoom_in = QPushButton("Zoom In")
            zoom_layout.addWidget(zoom_out)
            zoom_layout.addWidget(zoom_reset)
            zoom_layout.addWidget(zoom_in)
            layout.addLayout(zoom_layout)

            original_pixmap = pixmap
            zoom_level = 1.0

            def update_image():
                new_width = int(original_pixmap.width() * zoom_level)
                new_height = int(original_pixmap.height() * zoom_level)
                scaled_pixmap = original_pixmap.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                image_label.setPixmap(scaled_pixmap)
                image_label.resize(scaled_pixmap.size())

            def zoom_in_action():
                nonlocal zoom_level
                zoom_level *= 1.25
                update_image()

            def zoom_out_action():
                nonlocal zoom_level
                zoom_level *= 0.8
                update_image()

            def zoom_reset_action():
                nonlocal zoom_level
                zoom_level = 1.0
                update_image()

            zoom_in.clicked.connect(zoom_in_action)
            zoom_out.clicked.connect(zoom_out_action)
            zoom_reset.clicked.connect(zoom_reset_action)
            update_image()

            preview_dialog.setMinimumSize(400, 300)
            preview_dialog.resize(800, 600)
            preview_dialog.exec_()

        except Exception as e:
            logger.error(f"Error displaying image: {e}")
            QMessageBox.critical(self, "Error", f"Error displaying image: {e}")

    def show_paginated_document(self, filename: str, content: bytes, filetype: str):
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

            if not self.doc_renderer.load_document(content, filetype):
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
                if hasattr(self, 'doc_renderer'):
                    self.doc_renderer.close()
                    delattr(self, 'doc_renderer')

            doc_dialog.finished.connect(close_document_renderer)
            self.doc_renderer.render_page(0)

            # Set initial window size
            doc_dialog.resize(800, 800)
            doc_dialog.exec_()

        except Exception as e:
            logger.error(f"Error opening document {filename}: {e}")
            QMessageBox.critical(self, "Error", f"Error opening document: {e}")
            if hasattr(self, 'doc_renderer'):
                self.doc_renderer.close()
                delattr(self, 'doc_renderer')

    def close_document_renderer(self):
        """Closes the document renderer and releases resources."""
        if self.doc_renderer:
            self.doc_renderer.close()
            self.doc_renderer = None

    def show_text(self, data: bytes, filename: str):
        """Display text content in a scrollable editor with enhanced features."""
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError as e:
            logger.error(f"Failed to decode text content: {e}")
            text = "Unable to decode text content."

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Text Preview: {filename}")
        layout = QVBoxLayout(dlg)
        
        # Configure text editor with monospace font
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
        
        # Create button layout
        button_layout = QHBoxLayout()
        
        # Fullscreen toggle button
        btn_fullscreen = QPushButton("Full Screen (F11)")
        btn_fullscreen.clicked.connect(lambda: self.toggle_fullscreen(dlg, btn_fullscreen))
        
        # Close dialog button
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dlg.accept)
        
        # Add widgets to layouts
        button_layout.addWidget(btn_fullscreen)
        button_layout.addStretch()
        button_layout.addWidget(btn_close)
        
        layout.addWidget(editor)
        layout.addLayout(button_layout)
        
        # Window configuration
        dlg.resize(800, 600)
        dlg.setMinimumSize(400, 300)
        
        # Keyboard shortcut for fullscreen
        QShortcut(Qt.Key_F11, dlg).activated.connect(
            lambda: self.toggle_fullscreen(dlg, btn_fullscreen)
        )
        
        dlg.exec_()
        
    def toggle_fullscreen(self, dialog: QDialog, button: QPushButton):
        """Toggle fullscreen mode for the dialog."""
        if dialog.isFullScreen():
            dialog.showNormal()
            button.setText("Full Screen (F11)")
        else:
            dialog.showFullScreen()
            button.setText("Exit Full Screen (F11)")

    def play_audio(self, file_obj):
        """Play an audio file directly from the item with enhanced controls."""
        try:
            audio_url = file_obj.url
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Audio Player: {file_obj.name}")
            dialog.setMinimumWidth(400)
            layout = QVBoxLayout()
            
            # Create AudioPlayerHandler to manage player lifecycle
            class AudioPlayerHandler(QObject):
                def __init__(self, parent_dialog):
                    super().__init__()
                    self.player = QMediaPlayer()
                    self.parent_dialog = parent_dialog
                    # Store signal connections for safe disconnection
                    self.connections = []
                    
                def connect_signal(self, signal, slot):
                    # Connect signal and store the connection for later disconnection
                    signal.connect(slot)
                    self.connections.append((signal, slot))
                    
                def cleanup(self):
                    # Safely disconnect all stored connections
                    for signal, slot in self.connections:
                        try:
                            signal.disconnect(slot)
                        except (TypeError, RuntimeError):
                            # Ignore disconnection errors
                            pass
                    self.player.stop()
                    
            # Create handler and keep reference to prevent deletion
            player_handler = AudioPlayerHandler(dialog)
            dialog.player_handler = player_handler  # Store reference in dialog
            player = player_handler.player
            player.setMedia(QMediaContent(QUrl(audio_url)))
            
            # Add time display
            time_layout = QHBoxLayout()
            current_time_label = QLabel("0:00")
            duration_label = QLabel("0:00")
            time_layout.addWidget(current_time_label)
            time_layout.addStretch()
            time_layout.addWidget(duration_label)
            layout.addLayout(time_layout)
            
            # Add progress slider
            progress_slider = QSlider(Qt.Horizontal)
            progress_slider.setRange(0, 0)
            
            # Connect slider position change with specific function
            def on_slider_moved(position):
                player.setPosition(position)
            progress_slider.sliderMoved.connect(on_slider_moved)
            layout.addWidget(progress_slider)
            
            # Control buttons layout
            controls_layout = QHBoxLayout()
            
            # Play/Pause button with icon switching
            play_pause_btn = QPushButton("Play")
            is_playing = False
            
            def toggle_play_pause():
                nonlocal is_playing
                if is_playing:
                    player.pause()
                    play_pause_btn.setText("Play")
                    is_playing = False
                else:
                    player.play()
                    play_pause_btn.setText("Pause")
                    is_playing = True
                    
            play_pause_btn.clicked.connect(toggle_play_pause)
            controls_layout.addWidget(play_pause_btn)
            
            # Stop button
            stop_btn = QPushButton("Stop")
            def stop_playback():
                nonlocal is_playing
                player.stop()
                play_pause_btn.setText("Play")
                is_playing = False
                
            stop_btn.clicked.connect(stop_playback)
            controls_layout.addWidget(stop_btn)
            
            # Volume control
            volume_layout = QHBoxLayout()
            volume_label = QLabel("Volume:")
            volume_slider = QSlider(Qt.Horizontal)
            volume_slider.setRange(0, 100)
            volume_slider.setValue(70)  # Default volume at 70%
            player.setVolume(70)
            
            # Connect volume slider with specific function
            def on_volume_changed(value):
                player.setVolume(value)
            volume_slider.valueChanged.connect(on_volume_changed)
            
            volume_layout.addWidget(volume_label)
            volume_layout.addWidget(volume_slider)
            
            # Add layouts to main layout
            layout.addLayout(controls_layout)
            layout.addLayout(volume_layout)
            
            # Status label
            status_label = QLabel("Ready")
            layout.addWidget(status_label)
            
            # Signal handlers with safety checks
            def update_duration(duration):
                # Only update if dialog is still visible
                if dialog.isVisible():
                    progress_slider.setRange(0, duration)
                    minutes, seconds = divmod(duration // 1000, 60)
                    duration_label.setText(f"{minutes}:{seconds:02d}")
                
            def update_position(position):
                # Only update if dialog is still visible
                if dialog.isVisible():
                    if progress_slider.isVisible() and not progress_slider.isSliderDown():
                        progress_slider.setValue(position)
                    if current_time_label.isVisible():
                        minutes, seconds = divmod(position // 1000, 60)
                        current_time_label.setText(f"{minutes}:{seconds:02d}")
                
            def handle_state_changed(state):
                # Only update if dialog is still visible
                if dialog.isVisible() and status_label.isVisible():
                    if state == QMediaPlayer.PlayingState:
                        status_label.setText("Playing")
                    elif state == QMediaPlayer.PausedState:
                        status_label.setText("Paused")
                    elif state == QMediaPlayer.StoppedState:
                        status_label.setText("Stopped")
                    
            def handle_error():
                # Only update if dialog is still visible
                if dialog.isVisible() and status_label.isVisible():
                    error_msg = player.errorString()
                    status_label.setText(f"Error: {error_msg}")
                    logger.error(f"Media player error: {error_msg}")
            
            # Connect signals using our tracking method
            player_handler.connect_signal(player.durationChanged, update_duration)
            player_handler.connect_signal(player.positionChanged, update_position)
            player_handler.connect_signal(player.stateChanged, handle_state_changed)
            player_handler.connect_signal(player.error, handle_error)
            
            # Set layout and execute dialog
            dialog.setLayout(layout)
            
            # Important: Properly clean up when dialog is closed or rejected
            dialog.finished.connect(player_handler.cleanup)
            dialog.rejected.connect(player_handler.cleanup)
            
            dialog.exec_()
            
        except Exception as e:
            logger.error(f"Error playing audio: {e}")
            QMessageBox.critical(self, "Error", f"Error playing audio: {e}")