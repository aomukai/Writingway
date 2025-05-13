from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QGroupBox, 
                             QFormLayout, QDateEdit, QComboBox, QCheckBox, QListWidget, QHBoxLayout, 
                             QListWidgetItem, QAbstractItemView, QMessageBox, QDialog, QProgressDialog,
                             QGridLayout, QSizePolicy)
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QPixmap, QCursor
from internetarchive import search_items, download
from .ia_item_details_dialog import ItemDetailsDialog
import logging
import time
import webbrowser
from typing import List
from pathlib import Path

logger = logging.getLogger("ArchiveViewer")

class SearchWorker(QThread):
    """Worker thread for searching items without blocking the UI."""
    results_signal = pyqtSignal(list)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, query, session):
        super().__init__()
        self.query = query
        self.session = session
        self.is_cancelled = False

    def run(self):
        """Perform a basic search using Archive.org Advanced Search only."""
        try:
            results = []
            for result in search_items(
                self.query,
                fields=['identifier', 'title', 'mediatype'],
                archive_session=self.session
            ):
                if self.is_cancelled:
                    self.finished_signal.emit(False, "Search cancelled by user")
                    return

                results.append(result)
                if len(results) % 10 == 0:
                    self.results_signal.emit(results[-10:])
                    time.sleep(0.01)

            if results and len(results) % 10 != 0:
                self.results_signal.emit(results[-(len(results) % 10):])

            self.finished_signal.emit(True, f"Found {len(results)} results")

        except Exception as e:
            logger.error(f"Search failed: {e}")
            self.finished_signal.emit(False, f"Search failed: {str(e)}")

    def cancel(self):
        self.is_cancelled = True

class DownloadWorker(QThread):
    """Worker thread for downloading items without blocking the UI."""
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, identifiers: List[str], session, dest_dir: Path, options=None):
        super().__init__()
        self.identifiers = identifiers
        self.session = session
        self.dest_dir = dest_dir
        self.options = options or {}
        self.is_cancelled = False

    def run(self):
        total_items = len(self.identifiers)
        failed = []

        for i, identifier in enumerate(self.identifiers):
            if self.is_cancelled:
                self.finished_signal.emit(False, "Download cancelled by user")
                return

            self.progress_signal.emit(f"Downloading item {i + 1} of {total_items}: {identifier}")
            try:
                download(
                    identifier,
                    verbose=True,
                    archive_session=self.session,
                    destdir=str(self.dest_dir),
                    checksum=self.options.get('checksum', False),
                    checksum_archive=self.options.get('checksum_archive', False)
                )
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error downloading item {identifier}: {e}")
                failed.append((identifier, str(e)))
                # Continue with next item instead of aborting
                continue

        if failed:
            failed_list = ", ".join(id for id, unused in failed)
            self.finished_signal.emit(False, f"Some items failed to download: {failed_list}")
        else:
            self.finished_signal.emit(True, "All items downloaded successfully")

    def cancel(self):
        self.is_cancelled = True



class ProgressDialog(QProgressDialog):
    """Custom progress dialog that doesn't show percentage."""
    def __init__(self, title, message, cancel_button_text, parent=None):
        super().__init__(message, cancel_button_text, 0, 0, parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModal)
        self.setMinimumDuration(0)
        self.setCancelButton(None)  # Remove default cancel button
        self.setAutoClose(False)
        self.setAutoReset(False)
        
        # Set a fixed size
        self.setMinimumWidth(400)
        
        # Customizing appearance
        self.setStyleSheet("""
            QProgressDialog {
                background-color: #f5f5f5;
                border: 1px solid #dcdcdc;
                border-radius: 5px;
            }
            QLabel {
                font-size: 12px;
                color: #333333;
            }
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        
        # Custom cancel button
        self.cancel_btn = QPushButton(cancel_button_text)
        self.setCancelButton(self.cancel_btn)


class SearchDownloadTab(QWidget):
    """Tab for searching and downloading items from Internet Archive."""
    def __init__(self, session, download_dir, parent=None):
        super().__init__(parent)
        self.session = session
        self.download_dir = download_dir
        self.search_worker = None
        self.download_worker = None
        self.progress_dialog = None
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Main search section
        search_section = QHBoxLayout()
        self.search_query = QLineEdit()
        self.search_query.setPlaceholderText("Enter a search phrase, or leave blank to search the entire collection.")
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.perform_search)
        search_section.addWidget(self.search_query, 4)  # Proportion 4
        search_section.addWidget(self.search_btn, 1)    # Proportion 1

        # Advanced search section
        self.advanced_search_group = QGroupBox("Advanced Search Options")
        advanced_layout = QGridLayout()  # Changed to grid layout for better alignment

        # Date filters
        self.date_from = QDateEdit()
        self.date_from.setDate(QDate.currentDate().addYears(-1))
        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate())

        # File type combo box
        self.file_type = QComboBox()
        self.file_type.addItems([
            "All",
            "texts",
            "audio",
            "movies",
            "image",
            "web",
            "software",
            "data",
            "collection",
            "etree",
            "other"
        ])

        # Collection and uploader inputs
        self.collection = QLineEdit()
        self.collection.setPlaceholderText("e.g., internetarchivebooks")
        self.uploader = QLineEdit()
        self.uploader.setPlaceholderText("Username")

        # Add widgets to grid layout with proper positioning
        advanced_layout.addWidget(QLabel("From Date:"), 0, 0)
        advanced_layout.addWidget(self.date_from, 0, 1)
        advanced_layout.addWidget(QLabel("To Date:"), 0, 2)
        advanced_layout.addWidget(self.date_to, 0, 3)

        advanced_layout.addWidget(QLabel("File Type:"), 1, 0)
        advanced_layout.addWidget(self.file_type, 1, 1)
        advanced_layout.addWidget(QLabel("Collection:"), 1, 2)
        advanced_layout.addWidget(self.collection, 1, 3)

        advanced_layout.addWidget(QLabel("Uploader:"), 2, 0)
        advanced_layout.addWidget(self.uploader, 2, 1)

        # Create and add the link button container under the Collection and next to Uploader fields
        about_container = QWidget()
        about_layout = QHBoxLayout(about_container)
        about_layout.setContentsMargins(0, 0, 0, 0)
        about_layout.setSpacing(5)  # Small spacing between label and link

        # Create and add the label
        about_label = QLabel("Collection:")
        about_layout.addWidget(about_label)

        # Create and add the link button
        self.collection_description_link = QPushButton("Texts contributed by the community.")
        self.collection_description_link.setStyleSheet(
            "border: none; text-decoration: underline; color: blue; text-align: left;"
        )
        self.collection_description_link.setCursor(QCursor(Qt.PointingHandCursor))
        self.collection_description_link.clicked.connect(self.open_collection_description)
        self.collection_description_link.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Fixed
        )  # Fixed size policy
        about_layout.addWidget(self.collection_description_link)
        about_layout.addStretch(1)

        advanced_layout.addWidget(about_container, 2, 2, 1, 2)

        # Checkboxes with better layout
        checkboxes_layout = QHBoxLayout()
        self.checksum_checkbox = QCheckBox("Check Sum")
        self.checksum_checkbox.setToolTip(
            "Verifies downloaded file integrity. Ensures the file is complete and identical to the original source."
        )
        self.checksum_archive_checkbox = QCheckBox("Checksum Archive")
        self.checksum_archive_checkbox.setToolTip(
            "Verifies archive integrity before extraction. Prevents errors from corrupted ZIP, RAR or 7z files."
        )
        checkboxes_layout.addWidget(self.checksum_checkbox)
        checkboxes_layout.addWidget(self.checksum_archive_checkbox)
        checkboxes_layout.addStretch(1)  # Push checkboxes to the left
        advanced_layout.addLayout(checkboxes_layout, 3, 0, 1, 4)  # Span across all columns

        self.advanced_search_group.setLayout(advanced_layout)

        # Search results section
        results_label = QLabel("Results:")
        self.search_results = QListWidget()
        self.search_results.itemDoubleClicked.connect(self.open_item_details)
        self.search_results.setIconSize(QSize(16, 16))

        # Buttons for select/deselect and download in a horizontal layout
        action_buttons_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all_items)
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self.deselect_all_items)
        self.download_selected_btn = QPushButton("Download Selected")
        self.download_selected_btn.clicked.connect(self.perform_download_selected)
        action_buttons_layout.addWidget(self.select_all_btn)
        action_buttons_layout.addWidget(self.deselect_all_btn)
        action_buttons_layout.addStretch(1)
        action_buttons_layout.addWidget(self.download_selected_btn)

        # Assemble the main layout
        layout.addWidget(QLabel("Query:"))
        layout.addLayout(search_section)
        layout.addWidget(self.advanced_search_group)
        layout.addWidget(results_label)
        layout.addWidget(self.search_results)
        layout.addLayout(action_buttons_layout)
        
    def open_collection_description(self):
        """Open the collection description page in the default web browser."""
        webbrowser.open("https://archive.org/details/opensource?tab=about")

    def select_all_items(self):
        """Select all items in the search results list."""
        for i in range(self.search_results.count()):
            item = self.search_results.item(i)
            item.setCheckState(Qt.Checked)

    def deselect_all_items(self):
        """Deselect all items in the search results list."""
        for i in range(self.search_results.count()):
            item = self.search_results.item(i)
            item.setCheckState(Qt.Unchecked)

    def get_mediatype_icon(self, mediatype):
        """Get an appropriate icon for the media type."""
        # Audio
        if mediatype == 'audio':
            icon = QIcon.fromTheme("audio-x-generic")
            if not icon.isNull():
                return icon
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.cyan)
            return QIcon(pixmap)

        # Texts
        elif mediatype == 'texts':
            icon = QIcon.fromTheme("text-x-generic")
            if not icon.isNull():
                return icon
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.green)
            return QIcon(pixmap)

        # Image
        elif mediatype == 'image':
            icon = QIcon.fromTheme("image-x-generic")
            if not icon.isNull():
                return icon
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.yellow)
            return QIcon(pixmap)

        # Movies
        elif mediatype == 'movies':
            icon = QIcon.fromTheme("video-x-generic")
            if not icon.isNull():
                return icon
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.red)
            return QIcon(pixmap)

        # Software
        elif mediatype == 'software':
            icon = QIcon.fromTheme("application-x-executable")
            if not icon.isNull():
                return icon
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.magenta)
            return QIcon(pixmap)

        # Web archives
        elif mediatype == 'web':
            icon = QIcon.fromTheme("applications-internet")
            if not icon.isNull():
                return icon
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.blue)
            return QIcon(pixmap)

        # Live Music Archive
        elif mediatype == 'etree':
            icon = QIcon.fromTheme("media-optical")
            if not icon.isNull():
                return icon
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.darkYellow)
            return QIcon(pixmap)

        # Data sets
        elif mediatype == 'data':
            icon = QIcon.fromTheme("folder")
            if not icon.isNull():
                return icon
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.darkCyan)
            return QIcon(pixmap)

        # Collections
        elif mediatype == 'collection':
            icon = QIcon.fromTheme("folder")
            if not icon.isNull():
                return icon
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.darkGray)
            return QIcon(pixmap)

        # Other or unknown
        else:
            icon = QIcon.fromTheme("application-octet-stream")
            if not icon.isNull():
                return icon
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.gray)
            return QIcon(pixmap)

    def perform_search(self):
        """Search for items with advanced filters and display results with checkboxes."""
        base_query = self.search_query.text().strip()
        filters = []

        # date range
        if self.date_from.date().isValid() and self.date_to.date().isValid():
            from_date = self.date_from.date().toString("yyyy-MM-dd")
            to_date   = self.date_to.date().toString("yyyy-MM-dd")
            filters.append(f"date:[{from_date} TO {to_date}]")

        # mediatype filter
        if self.file_type.currentText() != "All":
            filters.append(f"mediatype:{self.file_type.currentText()}")

        # collection filter
        if self.collection.text().strip():
            filters.append(f"collection:{self.collection.text().strip()}")

        # uploader filter
        if self.uploader.text().strip():
            filters.append(f"uploader:{self.uploader.text().strip()}")

        # build the final query
        if base_query and filters:
            query = f"{base_query} AND {' AND '.join(filters)}"
        elif base_query:
            query = base_query
        elif filters:
            query = ' AND '.join(filters)
        else:
            QMessageBox.warning(self, "Warning", "Please provide a query or filters!")
            return

        # clear previous results
        self.search_results.clear()

        # show progress dialog
        self.progress_dialog = ProgressDialog(
            "Searching",
            "Searching for items. Please wait...",
            "Cancel",
            self
        )
        self.progress_dialog.canceled.connect(self.cancel_search)
        self.progress_dialog.show()

        # start the worker without any full-text support
        try:
            self.search_worker = SearchWorker(
                query,
                self.session
            )
            self.search_worker.results_signal.connect(self.update_search_results)
            self.search_worker.finished_signal.connect(self.search_finished)
            self.search_worker.start()
        except Exception as e:
            logger.error(f"Failed to start search: {e}")
            self.progress_dialog.close()
            QMessageBox.critical(self, "Error", f"Failed to start search: {str(e)}")

    def update_search_results(self, results):
        """Update the search results list as results come in."""
        for result in results:
            title = result.get('title', result['identifier'])
            identifier = result['identifier']
            mediatype = result.get('mediatype', '')
            
            item = QListWidgetItem(f"{title} ({identifier})")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            
            # Set an icon based on mediatype
            item.setIcon(self.get_mediatype_icon(mediatype))
            
            # Set tooltip explaining what the icon color means
            tooltip = f"Type: {mediatype}" if mediatype else "Type: unknown"
            item.setToolTip(tooltip)
            
            self.search_results.addItem(item)

    def search_finished(self, success, message):
        """Handle search completion."""
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
            
        if success:
            if self.search_results.count() == 0:
                QMessageBox.information(self, "Info", "No results found.")
            logger.info(f"Search completed: {message}")
        else:
            logger.error(f"Search failed: {message}")
            QMessageBox.critical(self, "Error", message)
            
        self.search_worker = None

    def cancel_search(self):
        """Cancel the current search operation."""
        if self.search_worker and self.search_worker.isRunning():
            logger.info("Cancelling search")
            self.search_worker.cancel()

    def open_item_details(self, item):
        """Open a dialog with details for the selected item."""
        identifier = item.text().split(' (')[-1][:-1]
        item_details = ItemDetailsDialog(identifier, self.session, self.download_dir)
        item_details.exec_()

    def perform_download_selected(self):
        """Download selected items to the internet_archive folder."""
        selected_items = []
        for i in range(self.search_results.count()):
            item = self.search_results.item(i)
            if item.checkState() == Qt.Checked:
                identifier = item.text().split(' (')[-1][:-1]
                selected_items.append(identifier)

        if not selected_items:
            QMessageBox.warning(self, "Warning", "No items selected for download")
            return

        # Create download options dictionary
        download_options = {
            'checksum': self.checksum_checkbox.isChecked(),
            'checksum_archive': self.checksum_archive_checkbox.isChecked()
        }
        
        # Create and show progress dialog
        self.progress_dialog = ProgressDialog(
            "Downloading", 
            f"Starting download of {len(selected_items)} items...", 
            "Cancel", 
            self
        )
        self.progress_dialog.canceled.connect(self.cancel_download)
        self.progress_dialog.show()
        
        # Create and start download worker
        try:
            self.download_worker = DownloadWorker(
                selected_items,
                self.session,
                self.download_dir,
                download_options
            )
            self.download_worker.progress_signal.connect(self.update_download_progress)
            self.download_worker.finished_signal.connect(self.download_finished)
            self.download_worker.start()
        except Exception as e:
            logger.error(f"Failed to start download: {e}")
            self.progress_dialog.close()
            QMessageBox.critical(self, "Error", f"Failed to start download: {str(e)}")

    def update_download_progress(self, message):
        """Update the progress dialog with download status."""
        if self.progress_dialog:
            self.progress_dialog.setLabelText(message)

    def download_finished(self, success, message):
        """Handle download completion."""
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
            
        if success:
            logger.info(f"Download completed: {message}")
            QMessageBox.information(self, "Success", message)
        else:
            logger.error(f"Download failed: {message}")
            QMessageBox.critical(self, "Error", message)
            
        self.download_worker = None

    def cancel_download(self):
        """Cancel the current download operation."""
        if self.download_worker and self.download_worker.isRunning():
            logger.info("Cancelling download")
            self.download_worker.is_cancelled = True
            self.download_worker.terminate()
            self.download_worker.wait()
            if self.progress_dialog:
                self.progress_dialog.close()