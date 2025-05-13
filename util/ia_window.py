from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QMenuBar, QAction, QMessageBox, QDialog, QScrollArea, QLabel
from PyQt5.QtCore import Qt
from internetarchive import get_session
from pathlib import Path
from .ia_search_download_tab import SearchDownloadTab
from .ia_downloaded_tab import DownloadedTab
from .ia_manage_tab import ManageTab
from .ia_login_tab import LoginTab
import configparser
import os

class IAWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Internet Archive")  # Set window title
        self.setGeometry(150, 150, 800, 600)     # Set window size and position

        # Initialize download directory
        self.download_dir = Path("internet_archive")
        self.download_dir.mkdir(exist_ok=True)

        # Attempt to get an authenticated session
        try:
            self.session = get_session()
        except Exception:
            self.session = None

        # Set up main layout
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Create and attach the menu bar
        self.create_menu_bar()

        # Set up tab widget
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # Initialize tabs
        self.search_download_tab = SearchDownloadTab(self.session, self.download_dir)
        self.downloaded_tab = DownloadedTab(self.download_dir)
        self.manage_tab = ManageTab(self.session)
        self.login_tab = LoginTab()
        self.login_tab.login_successful.connect(self.update_session)

        # Add tabs to the widget
        self.tabs.addTab(self.search_download_tab, "Search and Download")
        self.tabs.addTab(self.downloaded_tab, "Downloaded")
        self.tabs.addTab(self.manage_tab, "Manage")
        self.tabs.addTab(self.login_tab, "Login")

    def create_menu_bar(self):
        # Create a menu bar and attach it to this window
        menu_bar = QMenuBar(self)

        # Add "Help" menu to the menu bar
        help_menu = menu_bar.addMenu("Help")

        # Create "About" action and connect it to the show_app_info method
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_app_info)
        help_menu.addAction(about_action)

        # Set the menu bar on the layout
        self.layout.setMenuBar(menu_bar)

    def show_app_info(self):
        # Define HTML content for About dialog
        about_text = """
        <h1>About Archive Viewer</h1>
        <p>
            Archive Viewer is a desktop tool that streamlines access to the
            Internet Archive—a vast digital library of books, music, movies,
            websites, and more. Search, download, organize, and upload items
            all in one place.
        </p>

        <h2>Key Features</h2>
        <ul>
            <li><strong>Search & Download</strong><br>
                Enter keywords, apply filters (date range, file type, collection,
                author/uploader), then select and download items with optional
                checksum verification.
            </li>
            <li><strong>Manage Local Library</strong><br>
                View, open, or delete any files saved in your local
                <code>internet_archive</code> folder.
            </li>
            <li><strong>Upload & Metadata</strong><br>
                Upload new items or edit metadata by specifying an item identifier.
            </li>
            <li><strong>Secure Login</strong><br>
                Authenticate to enable uploads and metadata edits. Credentials
                are requested each session unless “Remember Me” is enabled.
            </li>
        </ul>

        <h2>Best Practices</h2>

        <h3>1. Searching Efficiently</h3>
        <ul>
            <li>
                Use precise keywords and the “Sort by” menu (relevance, date)
                to narrow results quickly. The underlying
                <code>internetarchive</code> library processes shorter, focused
                queries faster.
            </li>
        </ul>

        <h3>2. Organizing Downloads</h3>
        <ul>
            <li>
                Create subfolders inside your
                <code>internet_archive</code> directory to keep large collections tidy.
            </li>
            <li>
                Select multiple results for batch downloads to save time on
                large archival jobs.
            </li>
            <li>
                Monitor progress in the “Search & Download” tab—the log file
                <code>archive_viewer.log</code> records each step.
            </li>
            <li>
                In the “Downloaded” tab, sort by modification date to find
                recent files at the top.
            </li>
        </ul>

        <h3>3. Uploading & Troubleshooting</h3>
        <ul>
            <li>
                Split very large files (over 50 GB) into smaller parts to
                improve upload reliability.
            </li>
            <li>
                If an upload fails, review
                <code>archive_viewer.log</code> for error messages like
                “invalid metadata” or “connection timeout” to pinpoint issues.
            </li>
        </ul>

        <h3>4. Security Tips</h3>
        <ul>
            <li>
                Avoid storing credentials on shared or public machines.
                Use “Remember Me” only on personal devices.
            </li>
        </ul>

        <h3>5. Explore Before You Download</h3>
        <ul>
            <li>
                Double‑click any search result to view detailed metadata
                (size, format, uploader) before committing to download.
            </li>
        </ul>
        """

        dialog = QDialog(self)
        dialog.setWindowTitle("About Archive Viewer")
        dialog.resize(500, 600)

        scroll = QScrollArea(dialog)
        scroll.setWidgetResizable(True)

        container = QWidget()
        layout = QVBoxLayout(container)

        label = QLabel(about_text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText)
        label.setOpenExternalLinks(True)

        layout.addWidget(label)
        scroll.setWidget(container)

        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.addWidget(scroll)
        dialog.exec_()

    def update_session(self):
        """Update the session across tabs after successful login."""
        try:
            self.session = get_session()
            self.manage_tab.set_session(self.session)
            self.search_download_tab.session = self.session
        except Exception as e:
            print(f"Failed to update session: {e}")

    def closeEvent(self, event):
        """
        Before closing the application, if the configuration file exists,
        check the 'remember' flag and delete the file if it's set to False.
        """
        config_file = "config.ini"
        if os.path.exists(config_file):
            config = configparser.ConfigParser()
            config.read(config_file)
            if config.has_section("credentials"):
                remember = config.getboolean("credentials", "remember", fallback=False)
                if not remember:
                    try:
                        os.remove(config_file)
                    except Exception as e:
                        print(f"Could not delete configuration file: {e}")
        event.accept()
