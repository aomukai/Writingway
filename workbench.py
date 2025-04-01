import os
import json
import shutil
import json
import random
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QStackedWidget, QHBoxLayout, QVBoxLayout,
    QToolButton, QPushButton, QLabel, QMessageBox, QMenu, QFileDialog, QInputDialog
)
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from project_window.project_window import ProjectWindow
from settings.preferences import SettingsDialog
from settings.settings_manager import WWSettingsManager

# Define the file used for storing project data.
PROJECTS_FILE = "projects.json"

# Load version display

VERSION_FILE = "version.json"

def load_version():
    """Load version data from the version JSON file."""
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            QMessageBox.warning(None, "Load Version",
                                f"Error loading version: {e}")
    return {}

# Load settings at module level.
VERSION = load_version()


def load_projects():
    """Load project data from a JSON file. If the file does not exist, return default projects."""
    filepath = os.path.join(os.getcwd(), "Projects", PROJECTS_FILE)
    if not os.path.exists(filepath):
        oldpath = os.path.join(os.getcwd(), PROJECTS_FILE) # backward compatibility
        if (os.path.exists(oldpath)):
            os.rename(oldpath, filepath)
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            QMessageBox.warning(None, "Load Projects",
                                f"Error loading projects: {e}")
    # Default dummy project data.
    return [
        {"name": "My First Project", "cover": None},
        {"name": "Sci-Fi Epic", "cover": None},
        {"name": "Mystery Novel", "cover": None},
    ]


def save_projects(projects):
    """Save the project data to a JSON file."""
    filepath = os.path.join(os.getcwd(), "Projects", PROJECTS_FILE)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(projects, f, indent=4)
    except Exception as e:
        QMessageBox.warning(None, "Save Projects",
                            f"Error saving projects: {e}")


# Load projects at module level.
PROJECTS = load_projects()


class ProjectPostIt(QToolButton):
    """
    A custom QToolButton that displays the project cover.
    Left-click opens the project.
    Right-click shows a context menu with options.
    """

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.setup_ui()
        self.setToolTip(
            "Left-click: Open project\nRight-click: Options (Delete, Export, Stats, Edit Cover)")

    def setup_ui(self):
        default_size = QSize(300, 450)
        if self.project["cover"]:
            pixmap = QPixmap(self.project["cover"])
            pixmap = pixmap.scaled(
                default_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            pixmap = QPixmap(default_size)
            pixmap.fill(Qt.lightGray)
        icon = QIcon(pixmap)
        self.setIcon(icon)
        self.setIconSize(default_size)
        self.setFixedSize(default_size)
        self.setText("")
        self.setStyleSheet("QToolButton { margin: 0px; padding: 0px; }")

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        delete_action = menu.addAction("Delete Project")
        export_action = menu.addAction("Export Project")
        stats_action = menu.addAction("Project Statistics")
        cover_action = menu.addAction("Add Book Cover")
        action = menu.exec_(event.globalPos())
        if action == delete_action:
            confirm = QMessageBox.question(
                self, "Delete Project",
                f"Are you sure you want to delete '{self.project['name']}'?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                try:
                    PROJECTS.remove(self.project)
                    save_projects(PROJECTS)
                    QMessageBox.information(
                        self, "Delete Project", f"Project '{self.project['name']}' deleted.")
                    workbench = self.window()
                    if hasattr(workbench, "load_covers"):
                        workbench.load_covers()
                except Exception as e:
                    QMessageBox.warning(
                        self, "Delete Project", f"Error deleting project: {e}")
        elif action == export_action:
            QMessageBox.information(
                self, "Export Project",
                f"Export '{self.project['name']}' functionality will be implemented later."
            )
        elif action == stats_action:
            # Import statistics module
            try:
                from util.statistics import show_statistics
                
                # Project name from the workbench
                project_name = self.project['name']
                project_path = WWSettingsManager.get_project_path(project_name)
                
                # Print debugging info
                print(f"Looking for project: {project_name}")
                print(f"Current directory: {os.getcwd()}")
                
                if project_path and os.path.exists(project_path):
                    print(f"Found project at: {project_path}")
                else:
                    # Try direct paths
                    if os.path.exists(project_name) and os.path.isdir(project_name):
                        project_path = project_name
                        print(f"Found project at: {project_path}")
                    else:
                        sanitized_name = project_name.replace(" ", "")
                        if os.path.exists(sanitized_name) and os.path.isdir(sanitized_name):
                            project_path = sanitized_name
                            print(f"Found project at: {project_path}")
                
                # Ask the user if all automatic methods failed
                if not project_path:
                    from PyQt5.QtWidgets import QFileDialog
                    
                    # Set the initial directory to the Projects folder if it exists
                    initial_dir = WWSettingsManager.get_project_path() 
                    if not os.path.exists(initial_dir):
                        initial_dir = os.getcwd()
                    
                    # Let the user select the project directory
                    msg = f"Could not automatically find the directory for project '{project_name}'.\n"
                    msg += "Please select the project directory manually."
                    QMessageBox.information(self, "Select Project Directory", msg)
                    
                    project_path = QFileDialog.getExistingDirectory(
                        self, f"Select Directory for Project '{project_name}'", 
                        initial_dir
                    )
                    
                    if not project_path:
                        raise FileNotFoundError(f"User cancelled the project directory selection")
                
                # Make sure the directory exists and has some content
                if not os.path.exists(project_path) or not os.path.isdir(project_path):
                    raise FileNotFoundError(f"Invalid project directory: {project_path}")
                             
                # Show statistics dialog
                print(f"Opening statistics for project at: {project_path}")
                show_statistics(project_path)
                
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                
                QMessageBox.warning(
                    self, "Statistics Error",
                    f"Error loading project statistics: {str(e)}\n\n"
                    f"Project: '{self.project['name']}'\n"
                    f"Current directory: {os.getcwd()}\n\n"
                    f"Details (for debugging):\n{error_details}"
                )
        elif action == cover_action:
            try:
                self.add_book_cover()
                save_projects(PROJECTS)
            except Exception as e:
                QMessageBox.warning(self, "Error Adding Cover",
                                    f"Error adding book cover: {e}")

    def add_book_cover(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Book Cover", "", "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        destination_path = WWSettingsManager.get_project_path(self.project["name"])
        os.makedirs(destination_path, exist_ok=True)
        if file_path and os.path.dirname(file_path) != destination_path:
            file_path = os.path.relpath(shutil.copy2(file_path, destination_path))
        if file_path:
            self.project["cover"] = file_path
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "Invalid Image",
                                    "The selected file is not a valid image.")
                return
            default_size = QSize(300, 450)
            pixmap = pixmap.scaled(
                default_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon = QIcon(pixmap)
            self.setIcon(icon)
            self.setIconSize(default_size)



class ProjectCoverWidget(QWidget):
    """
    A composite widget that displays the project title above the cover.
    """
    openProject = pyqtSignal(str)

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self.titleLabel = QLabel(self.project["name"])
        self.titleLabel.setObjectName("projectTitleLabel")
        self.titleLabel.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.titleLabel)
        self.coverButton = ProjectPostIt(self.project)
        self.coverButton.clicked.connect(
            lambda: self.openProject.emit(self.project["name"]))
        layout.addWidget(self.coverButton)
        self.setLayout(layout)
        self.setFixedSize(300, 480)


class WorkbenchWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Writingway - Workbench")
        # Enable minimize and maximize buttons:
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        self.resize(640, 720)
        self.init_ui()
        self.apply_fixed_stylesheet()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)

        header_container = QWidget()
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)

        header_label = QLabel("")
        header_label.setObjectName("headerLabel")
        header_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        settings_button = QPushButton("")
        cog_icon_path = os.path.join("assets", "icons", "settings.svg")
        settings_button.setIcon(QIcon(cog_icon_path))
        settings_button.setToolTip(
            "Click here to configure global options (paths, fonts, themes, etc.)")
        settings_button.clicked.connect(self.open_settings)
        header_layout.addWidget(settings_button)
        layout.addWidget(header_container)

        carousel_container = QWidget()
        carousel_layout = QHBoxLayout(carousel_container)
        carousel_layout.setContentsMargins(0, 0, 0, 0)
        carousel_layout.setSpacing(10)

        self.left_button = QPushButton("")
        left_arrow_icon = QIcon(os.path.join(
            "assets", "icons", "chevron-left.svg"))
        self.left_button.setIcon(left_arrow_icon)
        self.left_button.setIconSize(QSize(32, 32))
        self.left_button.setFixedSize(60, 60)
        self.left_button.setToolTip("Previous Project")
        self.left_button.clicked.connect(self.show_previous)
        carousel_layout.addWidget(self.left_button)

        self.coverStack = QStackedWidget()
        self.coverStack.setFixedSize(300, 480)
        carousel_layout.addWidget(self.coverStack, stretch=1)

        self.right_button = QPushButton("")
        right_arrow_icon = QIcon(os.path.join(
            "assets", "icons", "chevron-right.svg"))
        self.right_button.setIcon(right_arrow_icon)
        self.right_button.setIconSize(QSize(32, 32))
        self.right_button.setFixedSize(60, 60)
        self.right_button.setToolTip("Next Project")
        self.right_button.clicked.connect(self.show_next)
        carousel_layout.addWidget(self.right_button)
        layout.addWidget(carousel_container)

        new_project_button = QPushButton("＋ New Project")
        new_project_button.setObjectName("newProjectButton")
        new_project_button.setFixedSize(200, 50)
        new_project_button.setToolTip("Create a brand-new project")
        new_project_button.clicked.connect(self.new_project)
        layout.addWidget(new_project_button, alignment=Qt.AlignCenter)
                
        # New: Random Quote display under the New Project button
        self.quoteLabel = QLabel()
        self.quoteLabel.setObjectName("quoteLabel")
        self.quoteLabel.setAlignment(Qt.AlignCenter)
        self.quoteLabel.setWordWrap(True)
        from PyQt5.QtWidgets import QSizePolicy
        self.quoteLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Set style without debugging border and with increased font size
        self.quoteLabel.setStyleSheet("font-style: italic; color: #666; margin: 10px;")
        # Load and format the random quote
        random_quote = self.load_random_quote()
        print("Loaded quote:", random_quote)
        quote_text = random_quote.get('text', 'No quote available')
        author_text = random_quote.get('author', 'Unknown')
        # Use <div> and <span> for better formatting and center alignment with increased font sizes
        formatted_text = (
            f"<html><body>"
            f"<div style='text-align:center;'>"
            f"<span style='font-size:18px;'>{quote_text}</span><br/>"
            f"<span style='font-size:14px; color:#444;'> {author_text}</span>"
            f"</div>"
            f"</body></html>"
        )
        self.quoteLabel.setText(formatted_text)
        self.quoteLabel.setTextFormat(Qt.RichText)
        # Set a larger minimum size to ensure the quote and author are visible
        self.quoteLabel.setMinimumSize(650, 150)
        self.quoteLabel.adjustSize()
        layout.addWidget(self.quoteLabel, alignment=Qt.AlignCenter)

        self.coverStack.currentChanged.connect(self.updateCoverStackSize)
        self.load_covers()

        # Add stretch to push the version label to the bottom
        layout.addStretch()

        # Add version display at the bottom right corner
        version_layout = QHBoxLayout()
        version_layout.addStretch()
        version_label = QLabel(f"Version: {VERSION.get('version', 'No Version Set')}")
        version_label.setAlignment(Qt.AlignRight)
        version_layout.addWidget(version_label)
        layout.addLayout(version_layout)
        
    def load_random_quote(self):
        """Load a random quote from quotes.json located in the same directory as the workbench."""
        quotes_file = os.path.join(os.getcwd(), "quotes.json")
        try:
            with open(quotes_file, "r", encoding="utf-8") as f:
                quotes = json.load(f)
            return random.choice(quotes)
        except Exception as e:
            print(f"Error loading quotes: {e}")
            return {"text": "No quote available", "author": ""}

    def apply_fixed_stylesheet(self):
        fixed_styles = """
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel#headerLabel {
                font-size: 22px;
                font-weight: 600;
                color: #333;
            }
            QLabel#projectTitleLabel {
                font-size: 14px;
                font-weight: 500;
                color: #333;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #ccc;
                border-radius: 6px;
                font-size: 14px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #e6e6e6;
            }
            QPushButton:pressed {
                background-color: #dcdcdc;
            }
            QPushButton#newProjectButton {
                font-size: 16px;
                font-weight: bold;
            }
            QToolButton {
                border: 2px solid #ccc;
                border-radius: 5px;
                background-color: #fff;
            }
            QToolButton:hover {
                background-color: #f0f0f0;
            }
        """
        self.setStyleSheet(fixed_styles)

    def open_settings(self):
        options = SettingsDialog(self)
        options.exec_()

    def updateCoverStackSize(self, index):
        fixed_width = 300
        fixed_height = 480
        self.coverStack.setFixedSize(fixed_width, fixed_height)

    def load_covers(self):
        while self.coverStack.count():
            widget = self.coverStack.widget(0)
            self.coverStack.removeWidget(widget)
            widget.deleteLater()
        if PROJECTS:
            for project in PROJECTS:
                cover_widget = ProjectCoverWidget(project)
                cover_widget.openProject.connect(self.open_project)
                self.coverStack.addWidget(cover_widget)
        else:
            new_project_btn = QToolButton()
            new_project_btn.setText("＋ New Project")
            new_project_btn.setFixedSize(300, 480)
            new_project_btn.clicked.connect(self.new_project)
            self.coverStack.addWidget(new_project_btn)
        self.updateCoverStackSize(self.coverStack.currentIndex())

    def show_previous(self):
        count = self.coverStack.count()
        if count == 0:
            return
        index = self.coverStack.currentIndex()
        new_index = (index - 1) % count
        self.coverStack.setCurrentIndex(new_index)

    def show_next(self):
        count = self.coverStack.count()
        if count == 0:
            return
        index = self.coverStack.currentIndex()
        new_index = (index + 1) % count
        self.coverStack.setCurrentIndex(new_index)

    def open_project(self, project_name):
        self.project_window = ProjectWindow(project_name)
        self.project_window.show()

    def new_project(self):
        name, ok = QInputDialog.getText(
            self, "New Project", "Enter new project name:")
        if ok and name.strip():
            new_project = {"name": name.strip(), "cover": None}
            PROJECTS.append(new_project)
            save_projects(PROJECTS)
            self.load_covers()
            self.coverStack.setCurrentIndex(len(PROJECTS) - 1)
            QMessageBox.information(
                self, "New Project", f"Project '{name}' created.")
        else:
            QMessageBox.information(
                self, "New Project", "Project creation cancelled.")


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    window = WorkbenchWindow()
    window.show()
    sys.exit(app.exec_())