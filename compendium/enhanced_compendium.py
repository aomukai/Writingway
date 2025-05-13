import os
import json
import re
import shutil
from datetime import datetime
from PyQt5.QtWidgets import (QMainWindow, QWidget, QToolBar, QSplitter, QTreeWidget, QTextEdit, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QComboBox, QPushButton, QListWidget, QTabWidget, QFileDialog, QMessageBox, QTreeWidgetItem,
                             QScrollArea, QFormLayout, QGroupBox, QInputDialog, QMenu, QColorDialog, QSizePolicy, QListWidgetItem)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings
from PyQt5.QtGui import QPixmap, QColor, QBrush

DEBUG = False

#############################
# ENHANCED COMPENDIUM CLASS #
#############################
class EnhancedCompendiumWindow(QMainWindow):
    # Define a signal that includes the project name
    compendium_updated = pyqtSignal(str)  # str is the project_name

    def __init__(self, project_name="default", parent=None):
        super().__init__(parent)
        self.dirty = False
        self.project_name = project_name
        self.controller = parent

        # 1) Create a QToolBar at the top
        self.toolbar = self.create_toolbar()
        self.addToolBar(self.toolbar)

        # 2) Set up the central widget (which holds the main layout and splitter)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # 3) Create the main splitter for the rest of the UI
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_layout.addWidget(self.main_splitter)

        # 4) Create the left (tree), center (content/tabs), and right (tags) panels
        self.create_tree_view()
        self.create_center_panel()
        self.create_right_panel()

        # 5) Set splitter proportions
        self.main_splitter.setStretchFactor(0, 1)  # Tree view
        self.main_splitter.setStretchFactor(1, 2)  # Content panel
        self.main_splitter.setStretchFactor(2, 1)  # Right panel

        # 6) Set up the compendium file and populate the UI
        self.setup_compendium_file()
        self.populate_compendium()
        self.connect_signals()

        # 7) Window title and size
        self.setWindowTitle(_("Enhanced Compendium - {}").format(self.project_name))
        self.resize(900, 700)

        # 8) Populate the project combo and connect its signal
        self.populate_project_combo()

        # 9) Read saved settings
        self.read_settings()
    
    def read_settings(self):
        """Read window and splitter settings from QSettings."""
        settings = QSettings("MyCompany", "WritingwayProject")
        geometry = settings.value("compendium_geometry")
        if geometry:
            self.restoreGeometry(geometry)
        window_state = settings.value("compendium_windowState")
        if window_state:
            self.restoreState(window_state)
        splitter_state = settings.value("compendium_mainSplitterState")
        if splitter_state:
            self.main_splitter.restoreState(splitter_state)

    def write_settings(self):
        """Write window and splitter settings to QSettings."""
        settings = QSettings("MyCompany", "WritingwayProject")
        settings.setValue("compendium_geometry", self.saveGeometry())
        settings.setValue("compendium_windowState", self.saveState())
        settings.setValue("compendium_mainSplitterState", self.main_splitter.saveState())

    def closeEvent(self, event):
        """Handle window close event to save settings and any unsaved changes."""
        if self.dirty and hasattr(self, 'current_entry') and hasattr(self, 'current_entry_item'):
            self.save_current_entry()
        self.write_settings()
        event.accept()
        # Emit the compendium_updated signal
        self.compendium_updated.emit(self.project_name)

    def mark_dirty(self):
        self.dirty = True
    
    def create_toolbar(self):
        toolbar = QToolBar(_("Project Toolbar"), self)
        toolbar.setObjectName("EnhToolBar_Main")
        label = QLabel(_("<b>Project:</b>"))
        toolbar.addWidget(label)
        self.project_combo = QComboBox()
        toolbar.addWidget(self.project_combo)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        toolbar.addWidget(spacer)
        return toolbar
    
    def populate_project_combo(self, project_name = None):
        """Populate the project pulldown with subdirectories in .\Projects."""
        projects_path = os.path.join(os.getcwd(), "Projects")
        if not os.path.exists(projects_path):
            os.makedirs(projects_path)
        # Get all project folders
        projects = [d for d in os.listdir(projects_path) if os.path.isdir(os.path.join(projects_path, d))]
        
        if project_name:
            self.project_name = project_name
        else:
            project_name = self.project_name

        # If there are other projects and "default" is among them, remove it.
        if projects and len(projects) > 1 and "default" in projects:
            projects.remove("default")
        
        # Block signals during update
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        
        if projects:
            projects.sort()
            self.project_combo.addItems(projects)
            # If self.project_name isn’t in the list, use the first project from the folder.
            index = self.project_combo.findText(self.sanitize(project_name))
            if index < 0:
                self.project_combo.setCurrentIndex(0)
                self.project_name = self.project_combo.currentText()
            else:
                self.project_combo.setCurrentIndex(index)
        else:
            # If there are no project folders, fall back to "default"
            self.project_combo.addItem("default")
            self.project_combo.setCurrentIndex(0)
            self.project_name = "default"
        
        self.project_combo.blockSignals(False)
        self.project_combo.currentTextChanged.connect(self.on_project_combo_changed)
        self.setWindowTitle(_("Enhanced Compendium - {}").format(self.project_name))
    
    def on_project_combo_changed(self, new_project):
        """Update the project and reload the compendium when a different project is selected."""
        self.change_project(new_project)
        self.select_first_entry()

    def select_first_entry(self):
        """Select the first non-category entry in the tree."""
        for i in range(self.tree.topLevelItemCount()):
            cat_item = self.tree.topLevelItem(i)
            if cat_item.childCount() > 0:
                entry_item = cat_item.child(0)
                if entry_item.data(0, Qt.UserRole) == "entry":
                    self.tree.setCurrentItem(entry_item)
                    return
    
    def change_project(self, new_project):
        self.project_name = new_project
        self.setWindowTitle(_("Enhanced Compendium - {}").format(self.project_name))
        self.setup_compendium_file()
        self.populate_compendium()

    def setup_compendium_file(self):
        """Set up the compendium file path for the selected project."""
        project_dir = os.path.join(os.getcwd(), "Projects", self.sanitize(self.project_name))
        self.compendium_file = os.path.join(project_dir, "compendium.json")
        if not os.path.exists(project_dir):
            os.makedirs(project_dir)
        if DEBUG:
            print("Loading compendium from:", self.compendium_file)
    
    def create_tree_view(self):
        """Create the left panel: a tree view (with a search bar) for categories and entries."""
        self.tree_widget = QWidget()
        tree_layout = QVBoxLayout(self.tree_widget)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText(_("Search entries and tags..."))
        tree_layout.addWidget(self.search_bar)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel(_("Compendium"))
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        tree_layout.addWidget(self.tree)
        self.main_splitter.addWidget(self.tree_widget)
    
    def create_center_panel(self):
        """Create the center panel with a header and a tabbed view for content, details, relationships, and images."""
        self.center_widget = QWidget()
        center_layout = QVBoxLayout(self.center_widget)
        
        # Header
        self.header_widget = QWidget()
        header_layout = QHBoxLayout(self.header_widget)
        self.entry_name_label = QLabel(_("No entry selected"))
        self.entry_name_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        header_layout.addWidget(self.entry_name_label)
        header_layout.addStretch()
        self.save_button = QPushButton(_("Save Changes"))
        header_layout.addWidget(self.save_button)
        center_layout.addWidget(self.header_widget)
        
        # Tabs
        self.tabs = QTabWidget()
        
        # Overview Tab
        self.overview_tab = QWidget()
        overview_layout = QVBoxLayout(self.overview_tab)
        self.editor = QTextEdit()
        self.editor.setPlaceholderText(_("This is the text the AI can see if you select this entry to be included in the prompt inside the context panel"))
        overview_layout.addWidget(self.editor)
        self.tabs.addTab(self.overview_tab, _("Overview"))
        self.tabs.setTabToolTip(0, _("this is the text the AI can see if you select this entry to be included in the prompt inside the context panel"))
        
        # Details Tab – now a single text editor
        self.details_editor = QTextEdit()
        self.details_editor.setPlaceholderText(_("Enter details about your entry here... (details about your entry the AI can't see - this info is only for you)"))
        self.tabs.addTab(self.details_editor, _("Details"))
        self.tabs.setTabToolTip(1, _("details about your entry the AI can't see - this info is only for you"))
        
        # Relationships Tab
        self.relationships_tab = QWidget()
        relationships_layout = QVBoxLayout(self.relationships_tab)
        add_rel_group = QGroupBox(_("Add Relationship"))
        add_rel_layout = QFormLayout(add_rel_group)
        self.rel_entry_combo = QComboBox()
        self.rel_type_combo = QComboBox()
        self.rel_type_combo.addItems([_("Friend"), _("Family"), _("Ally"), _("Enemy"), _("Acquaintance"), _("Other")])
        self.rel_type_combo.setEditable(True)
        self.add_rel_button = QPushButton(_("Add"))
        add_rel_layout.addRow(_("Related Entry:"), self.rel_entry_combo)
        add_rel_layout.addRow(_("Relationship Type:"), self.rel_type_combo)
        add_rel_layout.addRow("", self.add_rel_button)
        relationships_layout.addWidget(add_rel_group)
        self.relationships_list = QTreeWidget()
        self.relationships_list.setHeaderLabels([_("Entry"), _("Relationship Type")])
        self.relationships_list.setContextMenuPolicy(Qt.CustomContextMenu)
        relationships_layout.addWidget(self.relationships_list)
        self.tabs.addTab(self.relationships_tab, _("Relationships"))
        self.tabs.setTabToolTip(2, _("details about relationships between entries, not visible to the AI"))
        
        # Images Tab
        self.images_tab = QWidget()
        images_layout = QVBoxLayout(self.images_tab)
        image_controls = QWidget()
        image_controls_layout = QHBoxLayout(image_controls)
        self.add_image_button = QPushButton(_("Add Image"))
        self.remove_image_button = QPushButton(_("Remove Selected"))
        self.remove_image_button.setEnabled(False)
        image_controls_layout.addWidget(self.add_image_button)
        image_controls_layout.addWidget(self.remove_image_button)
        image_controls_layout.addStretch()
        images_layout.addWidget(image_controls)
        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_container = QWidget()
        self.image_layout = QVBoxLayout(self.image_container)
        self.image_scroll.setWidget(self.image_container)
        images_layout.addWidget(self.image_scroll)
        self.tabs.addTab(self.images_tab, _("Images"))
        self.tabs.setTabToolTip(3, _("add images for your entries - not visible to the AI"))
        
        center_layout.addWidget(self.tabs)
        self.main_splitter.addWidget(self.center_widget)
    
    def create_right_panel(self):
        """Create the right panel with tag management."""
        self.right_widget = QWidget()
        right_layout = QVBoxLayout(self.right_widget)
        
        tags_group = QGroupBox(_("Tags"))
        tags_layout = QVBoxLayout(tags_group)
        tag_input_layout = QHBoxLayout()
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText(_("Add new tag..."))
        tag_input_layout.addWidget(self.tag_input)
        self.add_tag_button = QPushButton("+")
        self.add_tag_button.setFixedWidth(30)
        self.add_tag_button.setToolTip(_("add a tag to your entry"))
        tag_input_layout.addWidget(self.add_tag_button)
        tags_layout.addLayout(tag_input_layout)
        self.tags_list = QListWidget()
        self.tags_list.setContextMenuPolicy(Qt.CustomContextMenu)
        tags_layout.addWidget(self.tags_list)
        right_layout.addWidget(tags_group)
        self.main_splitter.addWidget(self.right_widget)
    
    def populate_compendium(self):
        """Load compendium data from the file and populate the UI."""
        self.tree.clear()
        if not os.path.exists(self.compendium_file):
            if DEBUG:
                print("Compendium file not found, creating default structure")
            default_data = {
                "categories": [
                    {
                        "name": "Characters", 
                        "entries": [
                            {
                                "name": "Readme", 
                                "content": "This is a dummy entry. You can view and edit extended data in this window."
                            }
                        ]
                    }
                ],
                "extensions": {
                    "entries": {}
                }
            }
            try:
                with open(self.compendium_file, "w", encoding="utf-8") as f:
                    json.dump(default_data, f, indent=2)
                if DEBUG:
                    print("Created default compendium data at", self.compendium_file)
            except Exception as e:
                if DEBUG:
                    print("Error creating default compendium file:", e)
                QMessageBox.warning(self, _("Error"), _("Failed to create default compendium file: {}").format(str(e)))
                return
        
        try:
            with open(self.compendium_file, "r", encoding="utf-8") as f:
                self.compendium_data = json.load(f)
            if DEBUG:
                print("Loaded compendium data")
            
            if "extensions" not in self.compendium_data:
                self.compendium_data["extensions"] = {"entries": {}}
            elif "entries" not in self.compendium_data["extensions"]:
                self.compendium_data["extensions"]["entries"] = {}
            
            # Populate tree view from categories and set entry colors
            for cat in self.compendium_data.get("categories", []):
                cat_item = QTreeWidgetItem(self.tree, [cat.get("name", "Unnamed Category")])
                cat_item.setData(0, Qt.UserRole, "category")
                for entry in cat.get("entries", []):
                    entry_name = entry.get("name", "Unnamed Entry")
                    entry_item = QTreeWidgetItem(cat_item, [entry_name])
                    entry_item.setData(0, Qt.UserRole, "entry")
                    entry_item.setData(1, Qt.UserRole, entry.get("content", ""))
                    # Set the entry color based on the first tag if available
                    if entry_name in self.compendium_data["extensions"]["entries"]:
                        extended_data = self.compendium_data["extensions"]["entries"][entry_name]
                        tags = extended_data.get("tags", [])
                        if tags:
                            first_tag = tags[0]
                            tag_color = first_tag["color"] if isinstance(first_tag, dict) else "#000000"
                            entry_item.setForeground(0, QBrush(QColor(tag_color)))
                cat_item.setExpanded(True)
            self.update_relation_combo()
            
        except Exception as e:
            if DEBUG:
                print("Error loading compendium data:", e)
            QMessageBox.warning(self, _("Error"), _("Failed to load compendium data: {}").format(str(e)))
    
    def update_relation_combo(self):
        """Populate the relationship combo box with available entries."""
        self.rel_entry_combo.clear()
        for i in range(self.tree.topLevelItemCount()):
            cat_item = self.tree.topLevelItem(i)
            for j in range(cat_item.childCount()):
                entry_item = cat_item.child(j)
                entry_name = entry_item.text(0)
                self.rel_entry_combo.addItem(entry_name)
    
    def connect_signals(self):
        """Connect UI signals to their respective handlers."""
        self.tree.customContextMenuRequested.connect(self.show_tree_context_menu)
        self.tree.currentItemChanged.connect(self.on_item_changed)
        self.search_bar.textChanged.connect(self.filter_tree)
        self.save_button.clicked.connect(self.save_current_entry)
        self.add_tag_button.clicked.connect(self.add_tag)
        self.tag_input.returnPressed.connect(self.add_tag)
        self.editor.textChanged.connect(self.mark_dirty)
        self.details_editor.textChanged.connect(lambda: self.mark_dirty())
        self.tags_list.customContextMenuRequested.connect(self.show_tags_context_menu)
        self.add_rel_button.clicked.connect(self.add_relationship)
        self.relationships_list.customContextMenuRequested.connect(self.show_relationships_context_menu)
        self.relationships_list.itemDoubleClicked.connect(self.open_related_entry)
        self.add_image_button.clicked.connect(self.add_image)
        self.remove_image_button.clicked.connect(self.remove_selected_image)
    
    def show_tree_context_menu(self, pos):
        """Display context menu for the tree view."""
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        if item is None:
            action_new_category = menu.addAction(_("New Category"))
            action = menu.exec_(self.tree.viewport().mapToGlobal(pos))
            if action == action_new_category:
                self.new_category()
            return
        item_type = item.data(0, Qt.UserRole)
        if item_type == "category":
            action_new = menu.addAction(_("New Entry"))
            action_delete = menu.addAction(_("Delete Category"))
            action_rename = menu.addAction(_("Rename Category"))
            action_move_up = menu.addAction(_("Move Up"))
            action_move_down = menu.addAction(_("Move Down"))
            action = menu.exec_(self.tree.viewport().mapToGlobal(pos))
            if action == action_new:
                self.new_entry(item)
            elif action == action_delete:
                self.delete_category(item)
            elif action == action_rename:
                self.rename_item(item, "category")
            elif action == action_move_up:
                self.move_item(item, "up")
            elif action == action_move_down:
                self.move_item(item, "down")
        elif item_type == "entry":
            action_save = menu.addAction(_("Save Entry"))
            action_delete = menu.addAction(_("Delete Entry"))
            action_rename = menu.addAction(_("Rename Entry"))
            action_move_to = menu.addAction(_("Move To..."))
            action_move_up = menu.addAction(_("Move Up"))
            action_move_down = menu.addAction(_("Move Down"))
            action = menu.exec_(self.tree.viewport().mapToGlobal(pos))
            if action == action_save:
                self.save_entry(item)
            elif action == action_delete:
                self.delete_entry(item)
            elif action == action_rename:
                self.rename_item(item, "entry")
            elif action == action_move_to:
                self.move_entry(item)
            elif action == action_move_up:
                self.move_item(item, "up")
            elif action == action_move_down:
                self.move_item(item, "down")
    
    def show_tags_context_menu(self, pos):
        """Show context menu for tag actions: remove, move up, move down."""
        item = self.tags_list.itemAt(pos)
        if item is not None:
            menu = QMenu(self)
            action_remove = menu.addAction(_("Remove Tag"))
            action_move_up = menu.addAction(_("Move Up"))
            action_move_down = menu.addAction(_("Move Down"))
            action = menu.exec_(self.tags_list.viewport().mapToGlobal(pos))
            if action == action_remove:
                self.tags_list.takeItem(self.tags_list.row(item))
                self.mark_dirty()
                self.update_entry_indicator()
            elif action == action_move_up:
                row = self.tags_list.row(item)
                if row > 0:
                    self.tags_list.takeItem(row)
                    self.tags_list.insertItem(row - 1, item)
                    self.mark_dirty()
                    self.update_entry_indicator()
            elif action == action_move_down:
                row = self.tags_list.row(item)
                if row < self.tags_list.count() - 1:
                    self.tags_list.takeItem(row)
                    self.tags_list.insertItem(row + 1, item)
                    self.mark_dirty()
                    self.update_entry_indicator()
    
    def show_relationships_context_menu(self, pos):
        """Show context menu for relationship removal."""
        item = self.relationships_list.itemAt(pos)
        if item is not None:
            menu = QMenu(self)
            action_remove = menu.addAction(_("Remove Relationship"))
            action = menu.exec_(self.relationships_list.viewport().mapToGlobal(pos))
            if action == action_remove:
                self.relationships_list.takeTopLevelItem(self.relationships_list.indexOfTopLevelItem(item))
                self.mark_dirty()
    
    def add_tag(self):
        """Add a new tag to the current entry with a chosen color."""
        if not hasattr(self, 'current_entry'):
            return
        tag_text = self.tag_input.text().strip()
        if not tag_text:
            return
        for i in range(self.tags_list.count()):
            if self.tags_list.item(i).text().lower() == tag_text.lower():
                return
        color = QColorDialog.getColor(QColor("black"), self, _("Select Tag Color"))
        if not color.isValid():
            return
        item = QListWidgetItem(tag_text)
        item.setData(Qt.UserRole, color.name())
        item.setForeground(QBrush(color))
        item.setToolTip(_("right-click to move the tag within this list - this impacts the colour of your entry"))
        self.tags_list.addItem(item)
        self.tag_input.clear()
        self.mark_dirty()
        self.update_entry_indicator()
    
    def add_relationship(self):
        """Add a new relationship to the current entry."""
        if not hasattr(self, 'current_entry'):
            return
        related_entry = self.rel_entry_combo.currentText()
        rel_type = self.rel_type_combo.currentText()
        if not related_entry or not rel_type:
            return
        rel_item = QTreeWidgetItem([related_entry, rel_type])
        self.relationships_list.addTopLevelItem(rel_item)
        self.mark_dirty()
        self.update_entry_indicator()
    
    def open_related_entry(self, item, column):
        """Double-click a relationship to open the corresponding entry."""
        entry_name = item.text(0)
        self.find_and_select_entry(entry_name)

    def sanitize(self, text):
        return re.sub(r'\W+', '', text)    

    def add_image(self):
        """Add an image to the current entry."""
        if not hasattr(self, 'current_entry'):
            return
        file_path, unused = QFileDialog.getOpenFileName(self, _("Select Image"), "", "Image Files (*.png *.jpg *.jpeg *.gif *.bmp)")
        if not file_path:
            return
        project_dir = os.path.dirname(self.compendium_file)
        images_dir = os.path.join(project_dir, "images")
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unused, ext = os.path.splitext(file_path)
        sanitized_entry_name = self.sanitize(self.current_entry)
        new_filename = f"{sanitized_entry_name}_{timestamp}{ext}"
        new_path = os.path.join(images_dir, new_filename)
        try:
            shutil.copy2(file_path, new_path)
            if self.current_entry not in self.compendium_data["extensions"]["entries"]:
                self.compendium_data["extensions"]["entries"][self.current_entry] = {}
            if "images" not in self.compendium_data["extensions"]["entries"][self.current_entry]:
                self.compendium_data["extensions"]["entries"][self.current_entry]["images"] = []
            self.compendium_data["extensions"]["entries"][self.current_entry]["images"].append(new_filename)
            self.add_image_to_ui(new_path, new_filename)
            self.mark_dirty()
            self.update_entry_indicator()
        except Exception as e:
            if DEBUG:
                print("Error copying image:", e)
            QMessageBox.warning(self, _("Error"), _("Failed to copy image: {}").format(str(e)))
    
    def load_images(self, image_filenames):
        """Load images for the current entry."""
        self.clear_images()
        if not image_filenames:
            return
        project_dir = os.path.dirname(self.compendium_file)
        images_dir = os.path.join(project_dir, "images")
        for filename in image_filenames:
            image_path = os.path.join(images_dir, filename)
            if os.path.exists(image_path):
                self.add_image_to_ui(image_path, filename)
    
    def add_image_to_ui(self, image_path, filename):
        """Display an image in the UI."""
        image_container = QWidget()
        image_layout = QVBoxLayout(image_container)
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            max_width = 400
            if pixmap.width() > max_width:
                pixmap = pixmap.scaledToWidth(max_width, Qt.SmoothTransformation)
            image_label = QLabel()
            image_label.setPixmap(pixmap)
            image_label.setAlignment(Qt.AlignCenter)
            image_label.setProperty("filename", filename)
            image_label.setFrameShape(QLabel.Box)
            image_label.setObjectName("image")
            image_label.mousePressEvent = lambda event, label=image_label: self.select_image(label)
            image_layout.addWidget(image_label)
            name_label = QLabel(filename)
            name_label.setAlignment(Qt.AlignCenter)
            image_layout.addWidget(name_label)
            self.image_layout.addWidget(image_container)
        else:
            if DEBUG:
                print(f"Failed to load image: {image_path}")
    
    def select_image(self, label):
        """Select an image (for removal)."""
        for i in range(self.image_layout.count()):
            container = self.image_layout.itemAt(i).widget()
            for j in range(container.layout().count()):
                widget = container.layout().itemAt(j).widget()
                if isinstance(widget, QLabel) and widget.objectName() == "image":
                    widget.setStyleSheet("")
        label.setStyleSheet("border: 2px solid blue;")
        self.remove_image_button.setEnabled(True)
        self.selected_image = label
    
    def remove_selected_image(self):
        """Remove the selected image."""
        if not hasattr(self, 'selected_image'):
            return
        filename = self.selected_image.property("filename")
        if (hasattr(self, 'current_entry') and 
            self.current_entry in self.compendium_data["extensions"]["entries"] and
            "images" in self.compendium_data["extensions"]["entries"][self.current_entry]):
            if filename in self.compendium_data["extensions"]["entries"][self.current_entry]["images"]:
                self.compendium_data["extensions"]["entries"][self.current_entry]["images"].remove(filename)
            container = self.selected_image.parent()
            if container:
                container.deleteLater()
            self.remove_image_button.setEnabled(False)
            del self.selected_image
            self.mark_dirty()
            self.update_entry_indicator()
    
    def filter_tree(self, text):
        """Filter the tree view based on the search text (searches entry names and tags)."""
        if not text:
            for i in range(self.tree.topLevelItemCount()):
                cat_item = self.tree.topLevelItem(i)
                cat_item.setHidden(False)
                for j in range(cat_item.childCount()):
                    cat_item.child(j).setHidden(False)
            return
        text = text.lower()
        for i in range(self.tree.topLevelItemCount()):
            cat_item = self.tree.topLevelItem(i)
            cat_visible = False
            if text in cat_item.text(0).lower():
                cat_visible = True
            for j in range(cat_item.childCount()):
                entry_item = cat_item.child(j)
                entry_name = entry_item.text(0)
                match = False
                if text in entry_name.lower():
                    match = True
                elif entry_name in self.compendium_data["extensions"]["entries"]:
                    extended_data = self.compendium_data["extensions"]["entries"][entry_name]
                    for tag in extended_data.get("tags", []):
                        tag_name = tag["name"] if isinstance(tag, dict) else tag
                        if text in tag_name.lower():
                            match = True
                            break
                entry_item.setHidden(not match)
                if match:
                    cat_visible = True
            cat_item.setHidden(not cat_visible)
    
    def update_entry_indicator(self):
        """Update the entry indicator (coloring the entry name based on the first tag's color)."""
        if not hasattr(self, 'current_entry') or not hasattr(self, 'current_entry_item'):
            return
        entry_name = self.current_entry
        self.current_entry_item.setText(0, entry_name)
        color = QColor("black")
        if entry_name in self.compendium_data["extensions"]["entries"]:
            extended_data = self.compendium_data["extensions"]["entries"][entry_name]
            tags = extended_data.get("tags", [])
            if tags:
                first_tag = tags[0]
                tag_color = first_tag["color"] if isinstance(first_tag, dict) else "#000000"
                color = QColor(tag_color)
        self.current_entry_item.setForeground(0, QBrush(color))
    
    def save_entry(self, entry_item):
        """Save changes to a specific entry."""
        entry_name = entry_item.text(0)
        entry_item.setData(1, Qt.UserRole, self.editor.toPlainText())
        self.save_extended_data()
        self.save_compendium_to_file()
        self.dirty = False
    
    def save_current_entry(self):
        """Save the currently displayed entry (both basic and extended data)."""
        if not hasattr(self, 'current_entry') or not hasattr(self, 'current_entry_item'):
            return
        self.current_entry_item.setData(1, Qt.UserRole, self.editor.toPlainText())
        self.save_extended_data()
        self.save_compendium_to_file()
        self.dirty = False
    
    def save_extended_data(self):
        """Extract and save extended data for the current entry (details, tags, relationships, images)."""
        if not hasattr(self, 'current_entry'):
            return
        if self.current_entry not in self.compendium_data["extensions"]["entries"]:
            self.compendium_data["extensions"]["entries"][self.current_entry] = {}
        self.compendium_data["extensions"]["entries"][self.current_entry]["details"] = self.details_editor.toPlainText()
        tags = []
        for i in range(self.tags_list.count()):
            item = self.tags_list.item(i)
            tags.append({"name": item.text(), "color": item.data(Qt.UserRole)})
        if tags:
            self.compendium_data["extensions"]["entries"][self.current_entry]["tags"] = tags
        else:
            if "tags" in self.compendium_data["extensions"]["entries"][self.current_entry]:
                del self.compendium_data["extensions"]["entries"][self.current_entry]["tags"]
        relationships = []
        for i in range(self.relationships_list.topLevelItemCount()):
            item = self.relationships_list.topLevelItem(i)
            relationships.append({"name": item.text(0), "type": item.text(1)})
        if relationships:
            self.compendium_data["extensions"]["entries"][self.current_entry]["relationships"] = relationships
        else:
            if "relationships" in self.compendium_data["extensions"]["entries"][self.current_entry]:
                del self.compendium_data["extensions"]["entries"][self.current_entry]["relationships"]
        if not self.compendium_data["extensions"]["entries"][self.current_entry]:
            del self.compendium_data["extensions"]["entries"][self.current_entry]
        self.update_entry_indicator()
    
    def get_compendium_data(self):
        """Reconstruct the full compendium data."""
        data = {"categories": []}
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            cat_item = root.child(i)
            cat_data = {"name": cat_item.text(0), "entries": []}
            for j in range(cat_item.childCount()):
                entry_item = cat_item.child(j)
                entry_name = entry_item.text(0)
                cat_data["entries"].append({"name": entry_name, "content": entry_item.data(1, Qt.UserRole)})
            data["categories"].append(cat_data)
        data["extensions"] = self.compendium_data.get("extensions", {"entries": {}})
        return data
    
    def save_compendium_to_file(self):
        """Save the compendium data back to the file."""
        try:
            data = self.get_compendium_data()
            with open(self.compendium_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            if DEBUG:
                print("Saved compendium data to", self.compendium_file)
            
            # Emit signal with project name
            self.compendium_updated.emit(self.project_name)
        except Exception as e:
            if DEBUG:
                print("Error saving compendium data:", e)
            QMessageBox.warning(self, _("Error"), _("Failed to save compendium data: {}").format(str(e)))
    
    def new_category(self):
        name, ok = QInputDialog.getText(self, _("New Category"), _("Category name:"))
        if ok and name:
            cat_item = QTreeWidgetItem(self.tree, [name])
            cat_item.setData(0, Qt.UserRole, "category")
            self.save_compendium_to_file()
    
    def new_entry(self, category_item):
        name, ok = QInputDialog.getText(self, _("New Entry"), _("Entry name:"))
        if ok and name:
            entry_item = QTreeWidgetItem(category_item, [name])
            entry_item.setData(0, Qt.UserRole, "entry")
            entry_item.setData(1, Qt.UserRole, "")
            category_item.setExpanded(True)
            self.tree.setCurrentItem(entry_item)
            self.save_compendium_to_file()
    
    def delete_category(self, category_item):
        confirm = QMessageBox.question(self, _("Confirm Deletion"),
            _("Are you sure you want to delete the category '{}' and all its entries?").format(category_item.text(0)),
            QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            for i in range(category_item.childCount()):
                entry_item = category_item.child(i)
                entry_name = entry_item.text(0)
                if entry_name in self.compendium_data["extensions"]["entries"]:
                    del self.compendium_data["extensions"]["entries"][entry_name]
            root = self.tree.invisibleRootItem()
            root.removeChild(category_item)
            self.save_compendium_to_file()
    
    def delete_entry(self, entry_item):
        entry_name = entry_item.text(0)
        confirm = QMessageBox.question(self, _("Confirm Deletion"),
            _("Are you sure you want to delete the entry '{}'?").format(entry_name),
            QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            if entry_name in self.compendium_data["extensions"]["entries"]:
                del self.compendium_data["extensions"]["entries"][entry_name]
            parent = entry_item.parent()
            if parent:
                parent.removeChild(entry_item)
            self.save_compendium_to_file()
            if hasattr(self, 'current_entry') and self.current_entry == entry_name:
                self.clear_entry_ui()
    
    def rename_item(self, item, item_type):
        current_text = item.text(0)
        new_text, ok = QInputDialog.getText(self, _("Rename {}").format(item_type.capitalize()), _("New name:"), text=current_text)
        if ok and new_text:
            if item_type == "entry":
                old_name = current_text
                if old_name in self.compendium_data["extensions"]["entries"]:
                    self.compendium_data["extensions"]["entries"][new_text] = self.compendium_data["extensions"]["entries"][old_name]
                    del self.compendium_data["extensions"]["entries"][old_name]
                item.setText(0, new_text)
                if hasattr(self, 'current_entry') and self.current_entry == old_name:
                    self.current_entry = new_text
                    self.entry_name_label.setText(new_text)
            else:
                item.setText(0, new_text)
            self.save_compendium_to_file()
            if item_type == "entry":
                self.update_relation_combo()
    
    def move_item(self, item, direction):
        parent = item.parent() or self.tree.invisibleRootItem()
        index = parent.indexOfChild(item)
        if direction == "up" and index > 0:
            parent.takeChild(index)
            parent.insertChild(index - 1, item)
            self.tree.setCurrentItem(item)
        elif direction == "down" and index < parent.childCount() - 1:
            parent.takeChild(index)
            parent.insertChild(index + 1, item)
            self.tree.setCurrentItem(item)
        self.save_compendium_to_file()
    
    def move_entry(self, entry_item):
        from PyQt5.QtGui import QCursor
        menu = QMenu(self)
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            cat_item = root.child(i)
            if cat_item.data(0, Qt.UserRole) == "category":
                action = menu.addAction(cat_item.text(0))
                action.setData(cat_item)
        selected_action = menu.exec_(QCursor.pos())
        if selected_action is not None:
            target_category = selected_action.data()
            if target_category is not None:
                current_parent = entry_item.parent()
                if current_parent is not None:
                    current_parent.removeChild(entry_item)
                target_category.addChild(entry_item)
                target_category.setExpanded(True)
                self.tree.setCurrentItem(entry_item)
                self.save_compendium_to_file()
    
    def on_item_changed(self, current, previous):
        # Save changes to the previous entry if it exists and is dirty
        if previous is not None and previous.data(0, Qt.UserRole) == "entry" and self.dirty:
            self.save_entry(previous)

        if current is None:
            self.clear_entry_ui()
            return

        item_type = current.data(0, Qt.UserRole)
        if item_type == "entry":
            entry_name = current.text(0)
            self.load_entry(entry_name, current)
        else:
            self.clear_entry_ui()
    
    def load_entry(self, entry_name, entry_item):
        # Save changes to the current entry if it exists and is dirty
        if hasattr(self, 'current_entry') and hasattr(self, 'current_entry_item') and self.dirty:
            self.save_current_entry()

        self.current_entry = entry_name
        self.current_entry_item = entry_item
        self.entry_name_label.setText(entry_name)
        self.editor.blockSignals(True)
        content = entry_item.data(1, Qt.UserRole)
        self.editor.setPlainText(content)
        self.editor.blockSignals(False)
        has_extended = entry_name in self.compendium_data["extensions"]["entries"]
        if has_extended:
            extended_data = self.compendium_data["extensions"]["entries"][entry_name]
            self.details_editor.blockSignals(True)
            self.details_editor.setPlainText(extended_data.get("details", ""))
            self.details_editor.blockSignals(False)
            self.tags_list.clear()
            for tag in extended_data.get("tags", []):
                if isinstance(tag, dict):
                    tag_name = tag.get("name", "")
                    tag_color = tag.get("color", "#000000")
                else:
                    tag_name = tag
                    tag_color = "#000000"
                item = QListWidgetItem(tag_name)
                item.setData(Qt.UserRole, tag_color)
                item.setForeground(QBrush(QColor(tag_color)))
                item.setToolTip(_("right-click to move the tag within this list - this impacts the colour of your entry"))
                self.tags_list.addItem(item)
            self.relationships_list.clear()
            for rel in extended_data.get("relationships", []):
                rel_item = QTreeWidgetItem([rel.get("name", ""), rel.get("type", "")])
                self.relationships_list.addTopLevelItem(rel_item)
            self.load_images(extended_data.get("images", []))
        else:
            self.details_editor.clear()
            self.tags_list.clear()
            self.relationships_list.clear()
            self.clear_images()
        self.update_entry_indicator()
        self.dirty = False
        self.tabs.show()
    
    def clear_entry_ui(self):
        self.entry_name_label.setText(_("No entry selected"))
        self.editor.clear()
        self.details_editor.clear()
        self.tags_list.clear()
        self.relationships_list.clear()
        self.clear_images()
        self.dirty = False
        self.tabs.hide()
        if hasattr(self, 'current_entry'):
            del self.current_entry
        if hasattr(self, 'current_entry_item'):
            del self.current_entry_item
    
    def clear_images(self):
        while self.image_layout.count():
            child = self.image_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def open_with_entry(self, project_name, entry_name):
        """ make visible and raise window, then show the entry."""
        self.populate_project_combo(project_name)
        self.change_project(project_name)
        self.show()
        self.raise_()
        if entry_name:
            self.find_and_select_entry(entry_name)

    def find_and_select_entry(self, entry_name):
        """Search the tree and select an entry by name."""
        for i in range(self.tree.topLevelItemCount()):
            cat_item = self.tree.topLevelItem(i)
            for j in range(cat_item.childCount()):
                entry_item = cat_item.child(j)
                item_text = entry_item.text(0)
                if item_text == entry_name:
                    self.tree.setCurrentItem(entry_item)
                    return