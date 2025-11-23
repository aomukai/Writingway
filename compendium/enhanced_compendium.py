import re
from PyQt5.QtWidgets import (QMainWindow, QWidget, QToolBar, QSplitter, QTreeWidget, QTextEdit, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QComboBox, QPushButton, QListWidget, QTabWidget, QFileDialog, QMessageBox, QTreeWidgetItem,
                             QScrollArea, QFormLayout, QGroupBox, QInputDialog, QMenu, QColorDialog, QSizePolicy, QListWidgetItem)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QPixmap, QColor, QBrush, QFont
from compendium.compendium_manager import CompendiumManager, CompendiumEventBus
from settings.theme_manager import ThemeManager
import uuid

DEBUG = False

class EnhancedCompendiumWindow(QMainWindow):
    """
    Enhanced Compendium Window - A comprehensive interface for managing compendium data
    with categories, entries, tags, relationships, details, and images.
    """
    def __init__(self, parent=None):
        """
        Initialize the Enhanced Compendium Window.
        
        Args:
            project_name (str): Name of the project
            parent: Parent widget
        """
        super().__init__(parent)
        self.dirty = False  # Track unsaved changes
        self.project_name = "default" # project_name is set when we become visible
        self.controller = parent
        self.event_bus = CompendiumEventBus.get_instance()
        self.manager = CompendiumManager(self.project_name, event_bus=self.event_bus)
        self.event_bus.add_updated_listener(self.on_compendium_updated)
        self.compendium_data = {}

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

    def mark_dirty(self):
        """Mark the current entry as having unsaved changes."""
        self.dirty = True

    def create_toolbar(self):
        """Create the project selection toolbar at the top of the window."""
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

    def populate_project_combo(self, project_name=None):
        """
        Populate the project pulldown.
        
        Args:
            project_name (str, optional): Specific project to select
        """

        if project_name:
            self.project_name = project_name
        else:
            project_name = self.project_name

        self.project_combo.blockSignals(True)
        self.project_combo.clear()

        projects = self.parent().get_project_list()
        if projects:
            projects.sort()
            self.project_combo.addItems(projects)
            index = self.project_combo.findText(self.sanitize(project_name))
            if index < 0:
                self.project_combo.setCurrentIndex(0)
                self.project_name = self.project_combo.currentText()
            else:
                self.project_combo.setCurrentIndex(index)
        else:
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
        """Switch to a different project and reload its compendium data."""
        self.project_name = new_project
        self.manager = CompendiumManager(self.project_name, event_bus=self.event_bus)
        self.compendium_data = self.manager.load_data()
        self.setWindowTitle(_("Enhanced Compendium - {}").format(self.project_name))
        self.populate_compendium()

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
        """
        Create the center panel with a header and a tabbed view for content, details, 
        relationships, and images.
        """
        self.center_widget = QWidget()
        center_layout = QVBoxLayout(self.center_widget)

        # Header with entry name and save button
        self.header_widget = QWidget()
        header_layout = QHBoxLayout(self.header_widget)
        self.entry_name_label = QLabel(_("No entry selected"))
        self.entry_name_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        header_layout.addWidget(self.entry_name_label)
        header_layout.addStretch()
        self.save_button = QPushButton(_("Save Changes"))
        header_layout.addWidget(self.save_button)
        center_layout.addWidget(self.header_widget)

        self.tabs = QTabWidget()

        # Overview tab - content visible to AI
        self.overview_tab = QWidget()
        overview_layout = QVBoxLayout(self.overview_tab)
        self.editor = QTextEdit()
        self.editor.setPlaceholderText(_("This is the text the AI can see if you select this entry to be included in the prompt inside the context panel"))
        overview_layout.addWidget(self.editor)
        self.tabs.addTab(self.overview_tab, _("Overview"))
        self.tabs.setTabToolTip(0, _("this is the text the AI can see if you select this entry to be included in the prompt inside the context panel"))

        # Details tab - private notes not visible to AI
        self.details_editor = QTextEdit()
        self.details_editor.setPlaceholderText(_("Enter details about your entry here... (details about your entry the AI can't see - this info is only for you)"))
        self.tabs.addTab(self.details_editor, _("Details"))
        self.tabs.setTabToolTip(1, _("details about your entry the AI can't see - this info is only for you"))

        # Relationships tab
        self.relationships_tab = QWidget()
        relationships_layout = QVBoxLayout(self.relationships_tab)
        self.relationships_form = QGroupBox(_("Relationships"))
        form_layout = QFormLayout()
        self.relationship_combo = QComboBox()
        self.relationship_type = QLineEdit()
        self.add_relationship_button = QPushButton(_("Add Relationship"))
        form_layout.addRow(_("Related Entry:"), self.relationship_combo)
        form_layout.addRow(_("Relationship Type:"), self.relationship_type)
        form_layout.addRow(self.add_relationship_button)
        self.relationships_form.setLayout(form_layout)
        self.relationships_list = QTreeWidget()
        self.relationships_list.setHeaderLabels([_("Name"), _("Type")])
        relationships_layout.addWidget(self.relationships_form)
        relationships_layout.addWidget(self.relationships_list)
        self.tabs.addTab(self.relationships_tab, _("Relationships"))

        # Images tab
        self.images_tab = QTabWidget()
        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_widget = QWidget()
        self.image_layout = QHBoxLayout(self.image_widget)
        self.image_scroll.setWidget(self.image_widget)
        self.images_tab.addTab(self.image_scroll, _("Images"))
        self.add_image_button = QPushButton(_("Add Image"))
        images_layout = QVBoxLayout()
        images_layout.addWidget(self.images_tab)
        images_layout.addWidget(self.add_image_button)
        self.image_widget = QWidget()
        self.image_widget.setLayout(images_layout)
        self.tabs.addTab(self.image_widget, _("Images"))

        center_layout.addWidget(self.tabs)
        self.main_splitter.addWidget(self.center_widget)

    def create_right_panel(self):
        """Create the right panel for tags management."""
        self.right_widget = QWidget()
        right_layout = QVBoxLayout(self.right_widget)
        self.tags_form = QGroupBox(_("Tags"))
        form_layout = QFormLayout()
        self.tag_input = QLineEdit()
        self.tag_color_button = QPushButton(_("Choose Color"))
        self.add_tag_button = QPushButton(_("Add Tag"))
        form_layout.addRow(_("Tag:"), self.tag_input)
        form_layout.addRow(self.tag_color_button)
        form_layout.addRow(self.add_tag_button)
        self.tags_form.setLayout(form_layout)
        self.tags_list = QListWidget()
        self.tags_list.setContextMenuPolicy(Qt.CustomContextMenu)
        right_layout.addWidget(self.tags_form)
        right_layout.addWidget(self.tags_list)
        self.main_splitter.addWidget(self.right_widget)

    def connect_signals(self):
        """Connect all necessary signals for interactive functionality."""
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.currentItemChanged.connect(self.on_item_changed)
        self.search_bar.textChanged.connect(self.filter_tree)
        self.save_button.clicked.connect(self.save_current_entry)
        self.add_tag_button.clicked.connect(self.add_tag)
        self.tag_color_button.clicked.connect(self.choose_tag_color)
        self.tags_list.customContextMenuRequested.connect(self.show_tags_context_menu)
        self.add_relationship_button.clicked.connect(self.add_relationship)
        self.relationships_list.customContextMenuRequested.connect(self.show_relationships_context_menu)
        self.add_image_button.clicked.connect(self.add_image)
        self.editor.textChanged.connect(self.mark_dirty)
        self.details_editor.textChanged.connect(self.mark_dirty)

    def sanitize(self, text):
        """Sanitize text by removing non-word characters for safe filenames."""
        return re.sub(r'\W+', '', text)

    def populate_compendium(self):
        """Populate the tree view with compendium data from the manager."""
        selected_item_info = self.get_selected_item_info()
        self.tree.clear()
        bold_font = QFont()
        bold_font.setBold(True)
        self.compendium_data = self.manager.load_data()
        for cat in self.compendium_data.get("categories", []):
            cat_name = cat.get("name", "Unnamed Category")
            cat_item = QTreeWidgetItem(self.tree, [cat_name])
            cat_item.setData(0, Qt.UserRole, "category")
            cat_item.setBackground(0, QBrush(ThemeManager.get_category_background_color()))
            cat_item.setFont(0, bold_font)
            for entry in sorted(cat.get("entries", []), key=lambda e: e.get("name", "")):
                entry_name = entry.get("name", "Unnamed Entry")
                entry_item = QTreeWidgetItem(cat_item, [entry_name])
                entry_item.setData(0, Qt.UserRole, "entry")
                entry_item.setData(1, Qt.UserRole, entry.get("content", ""))
                entry_item.setData(2, Qt.UserRole, entry.get("uuid", str(uuid.uuid4())))
                cat_item.setExpanded(True)
        self.restore_selection(selected_item_info)
        self.update_relation_combo()

    def get_selected_item_info(self):
        """Return info about the currently selected item for preserving selection."""
        current_item = self.tree.currentItem()
        if not current_item:
            return None
        item_type = current_item.data(0, Qt.UserRole)
        item_name = current_item.text(0)
        if item_type == "entry":
            parent_item = current_item.parent()
            parent_name = parent_item.text(0) if parent_item else None
            return {"type": "entry", "name": item_name, "category": parent_name}
        return {"type": "category", "name": item_name}

    def restore_selection(self, selected_item_info):
        """Attempt to reselect the previously selected item after refresh."""
        if not selected_item_info:
            return
        item_type = selected_item_info["type"]
        item_name = selected_item_info["name"]
        if item_type == "category":
            for i in range(self.tree.topLevelItemCount()):
                cat_item = self.tree.topLevelItem(i)
                if cat_item.text(0) == item_name and cat_item.data(0, Qt.UserRole) == "category":
                    self.tree.setCurrentItem(cat_item)
                    return
        elif item_type == "entry":
            category_name = selected_item_info["category"]
            for i in range(self.tree.topLevelItemCount()):
                cat_item = self.tree.topLevelItem(i)
                if category_name and cat_item.text(0) != category_name:
                    continue
                for j in range(cat_item.childCount()):
                    entry_item = cat_item.child(j)
                    if entry_item.text(0) == item_name and entry_item.data(0, Qt.UserRole) == "entry":
                        self.tree.setCurrentItem(entry_item)
                        return
                if category_name and cat_item.text(0) == category_name:
                    if cat_item.childCount() > 0:
                        self.tree.setCurrentItem(cat_item.child(0))
                    else:
                        self.tree.setCurrentItem(cat_item)
                    return
        self.tree.clearSelection()

    def show_context_menu(self, pos):
        """Show context menu for tree items with appropriate actions."""
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        if item:
            item_type = item.data(0, Qt.UserRole)
            if item_type == "category":
                menu.addAction(_("New Entry"), lambda: self.new_entry(item))
                menu.addAction(_("Rename Category"), lambda: self.rename_item(item, "category"))
                menu.addAction(_("Delete Category"), lambda: self.delete_category(item))
            elif item_type == "entry":
                menu.addAction(_("Rename Entry"), lambda: self.rename_item(item, "entry"))
                menu.addAction(_("Delete Entry"), lambda: self.delete_entry(item))
                menu.addAction(_("Move Up"), lambda: self.move_item(item, "up"))
                menu.addAction(_("Move Down"), lambda: self.move_item(item, "down"))
                menu.addAction(_("Move to Category"), lambda: self.move_entry(item))
        else:
            menu.addAction(_("New Category"), self.new_category)
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def save_current_entry(self):
        """Save the current entry's data to the compendium."""
        if hasattr(self, 'current_entry') and hasattr(self, 'current_entry_item'):
            self.save_entry(self.current_entry_item)
            self.dirty = False

    def save_entry(self, entry_item):
        """Save the entry data to compendium_data and persist to file."""
        entry_name = entry_item.text(0)
        category_item = entry_item.parent()
        if not category_item:
            return
        category_name = category_item.text(0)
        content = self.editor.toPlainText()
        entry_item.setData(1, Qt.UserRole, content)
        for cat in self.compendium_data["categories"]:
            if cat.get("name") == category_name:
                for entry in cat.get("entries", []):
                    if entry.get("name") == entry_name:
                        entry["content"] = content
                        entry["uuid"] = entry_item.data(2, Qt.UserRole)
                        break
                else:
                    new_entry = {
                        "name": entry_name,
                        "content": content,
                        "uuid": entry_item.data(2, Qt.UserRole)
                    }
                    cat["entries"].append(new_entry)
                break
        if entry_name in self.compendium_data["extensions"]["entries"]:
            extended_data = self.compendium_data["extensions"]["entries"][entry_name]
            extended_data["details"] = self.details_editor.toPlainText()
            extended_data["tags"] = [
                {"name": self.tags_list.item(i).text(), "color": self.tags_list.item(i).data(Qt.UserRole)}
                for i in range(self.tags_list.count())
            ]
            extended_data["relationships"] = [
                {"name": self.relationships_list.topLevelItem(i).text(0), "type": self.relationships_list.topLevelItem(i).text(1)}
                for i in range(self.relationships_list.topLevelItemCount())
            ]
            extended_data["images"] = self.get_images()
        self.save_compendium_to_file()

    def save_compendium_to_file(self):
        """Save the compendium data back to the file via the manager."""
        try:
            self.manager.save_data(self.compendium_data)
            if DEBUG:
                print("Saved compendium data to", self.compendium_file)
        except Exception as e:
            if DEBUG:
                print("Error saving compendium data:", e)
            QMessageBox.warning(self, _("Error"), _("Failed to save compendium data: {}").format(str(e)))

    def new_category(self):
        """Create a new category in the compendium."""
        name, ok = QInputDialog.getText(self, _("New Category"), _("Category name:"))
        if ok and name:
            cat_item = QTreeWidgetItem(self.tree, [name])
            cat_item.setData(0, Qt.UserRole, "category")
            cat_item.setBackground(0, QBrush(ThemeManager.get_category_background_color()))
            cat_item.setFont(0, QFont("", weight=QFont.Bold))
            self.compendium_data["categories"].append({"name": name, "entries": []})
            self.save_compendium_to_file()

    def new_entry(self, category_item):
        """Create a new entry under the specified category."""
        name, ok = QInputDialog.getText(self, _("New Entry"), _("Entry name:"))
        if ok and name:
            entry_item = QTreeWidgetItem(category_item, [name])
            entry_item.setData(0, Qt.UserRole, "entry")
            entry_item.setData(1, Qt.UserRole, "")
            entry_item.setData(2, Qt.UserRole, str(uuid.uuid4()))
            self.compendium_data["extensions"]["entries"][name] = {"details": "", "tags": [], "relationships": [], "images": []}
            category_item.setExpanded(True)
            self.tree.setCurrentItem(entry_item)
            self.save_compendium_to_file()
            self.update_relation_combo()

    def delete_category(self, category_item):
        """Delete a category and all its entries after confirmation."""
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
            self.compendium_data["categories"] = [
                cat for cat in self.compendium_data["categories"] if cat.get("name") != category_item.text(0)
            ]
            self.save_compendium_to_file()
            self.update_relation_combo()

    def delete_entry(self, entry_item):
        """Delete an entry after confirmation."""
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
                for cat in self.compendium_data["categories"]:
                    if cat.get("name") == parent.text(0):
                        cat["entries"] = [e for e in cat.get("entries", []) if e.get("name") != entry_name]
                        break
            self.save_compendium_to_file()
            if hasattr(self, 'current_entry') and self.current_entry == entry_name:
                self.clear_entry_ui()
            self.update_relation_combo()

    def rename_item(self, item, item_type):
        """Rename a category or entry."""
        current_text = item.text(0)
        new_text, ok = QInputDialog.getText(self, _("Rename {}").format(item_type.capitalize()), _("New name:"), text=current_text)
        if ok and new_text:
            if item_type == "entry":
                old_name = current_text
                if old_name in self.compendium_data["extensions"]["entries"]:
                    self.compendium_data["extensions"]["entries"][new_text] = self.compendium_data["extensions"]["entries"][old_name]
                    del self.compendium_data["extensions"]["entries"][old_name]
                for cat in self.compendium_data["categories"]:
                    if cat.get("name") == item.parent().text(0):
                        for entry in cat.get("entries", []):
                            if entry.get("name") == old_name:
                                entry["name"] = new_text
                                break
                item.setText(0, new_text)
                if hasattr(self, 'current_entry') and self.current_entry == old_name:
                    self.current_entry = new_text
                    self.entry_name_label.setText(new_text)
            else:
                for cat in self.compendium_data["categories"]:
                    if cat.get("name") == current_text:
                        cat["name"] = new_text
                        break
                item.setText(0, new_text)
            self.save_compendium_to_file()
            if item_type == "entry":
                self.update_relation_combo()

    def move_item(self, item, direction):
        """Move an entry up or down within its category."""
        parent = item.parent() or self.tree.invisibleRootItem()
        index = parent.indexOfChild(item)
        if direction == "up" and index > 0:
            parent.takeChild(index)
            parent.insertChild(index - 1, item)
            self.tree.setCurrentItem(item)
            self.update_category_data(parent)
        elif direction == "down" and index < parent.childCount() - 1:
            parent.takeChild(index)
            parent.insertChild(index + 1, item)
            self.tree.setCurrentItem(item)
            self.update_category_data(parent)
        self.save_compendium_to_file()

    def update_category_data(self, parent):
        """Update category data to reflect the current order of items."""
        category_name = parent.text(0) if parent != self.tree.invisibleRootItem() else None
        if category_name:
            for cat in self.compendium_data["categories"]:
                if cat.get("name") == category_name:
                    new_entries = []
                    for i in range(parent.childCount()):
                        item = parent.child(i)
                        for entry in cat.get("entries", []):
                            if entry.get("name") == item.text(0):
                                new_entries.append(entry)
                                break
                    cat["entries"] = new_entries
                    break

    def move_entry(self, entry_item):
        """Move an entry to a different category via context menu."""
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
                    for cat in self.compendium_data["categories"]:
                        if cat.get("name") == current_parent.text(0):
                            cat["entries"] = [e for e in cat.get("entries", []) if e.get("name") != entry_item.text(0)]
                            break
                for cat in self.compendium_data["categories"]:
                    if cat.get("name") == target_category.text(0):
                        cat["entries"].append({
                            "name": entry_item.text(0),
                            "content": entry_item.data(1, Qt.UserRole),
                            "uuid": entry_item.data(2, Qt.UserRole)
                        })
                        break
                target_category.addChild(entry_item)
                target_category.setExpanded(True)
                self.tree.setCurrentItem(entry_item)
                self.save_compendium_to_file()

    def on_item_changed(self, current, previous):
        """Handle tree item selection changes, saving previous entry if dirty."""
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
        """
        Load all data for the selected entry into the UI panels.
        
        Args:
            entry_name (str): Name of the entry
            entry_item: The QTreeWidgetItem for this entry
        """
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
        """Clear all entry data from the UI panels."""
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
        """Clear all images from the images layout."""
        while self.image_layout.count():
            child = self.image_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def open_with_entry(self, project_name, entry_name):
        """Make visible and raise window, then show the entry."""
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

    def update_relation_combo(self):
        """Update the relationship combo box with all entry names."""
        self.relationship_combo.clear()
        entries = []
        for cat in self.compendium_data.get("categories", []):
            for entry in cat.get("entries", []):
                entries.append(entry.get("name", ""))
        entries.sort()
        self.relationship_combo.addItems(entries)

    def add_tag(self):
        """Add a new tag to the current entry."""
        tag_name = self.tag_input.text().strip()
        if tag_name and hasattr(self, 'current_entry'):
            tag_color = self.tag_color_button.property("current_color") or "#000000"
            item = QListWidgetItem(tag_name)
            item.setData(Qt.UserRole, tag_color)
            item.setForeground(QBrush(QColor(tag_color)))
            item.setToolTip(_("right-click to move the tag within this list - this impacts the colour of your entry"))
            self.tags_list.addItem(item)
            self.tag_input.clear()
            self.mark_dirty()

    def choose_tag_color(self):
        """Open a color dialog to choose a tag color."""
        color = QColorDialog.getColor()
        if color.isValid():
            self.tag_color_button.setProperty("current_color", color.name())
            self.tag_color_button.setStyleSheet(f"background-color: {color.name()};")
            self.mark_dirty()

    def show_tags_context_menu(self, pos):
        """Show context menu for tags list."""
        item = self.tags_list.itemAt(pos)
        if item:
            menu = QMenu(self)
            menu.addAction(_("Remove Tag"), lambda: self.remove_tag(item))
            menu.addAction(_("Move Up"), lambda: self.move_tag(item, "up"))
            menu.addAction(_("Move Down"), lambda: self.move_tag(item, "down"))
            menu.exec_(self.tags_list.viewport().mapToGlobal(pos))

    def remove_tag(self, item):
        """Remove a tag from the tags list."""
        row = self.tags_list.row(item)
        self.tags_list.takeItem(row)
        self.mark_dirty()

    def move_tag(self, item, direction):
        """Move a tag up or down in the tags list."""
        row = self.tags_list.row(item)
        if direction == "up" and row > 0:
            self.tags_list.takeItem(row)
            self.tags_list.insertItem(row - 1, item)
            self.tags_list.setCurrentItem(item)
        elif direction == "down" and row < self.tags_list.count() - 1:
            self.tags_list.takeItem(row)
            self.tags_list.insertItem(row + 1, item)
            self.tags_list.setCurrentItem(item)
        self.mark_dirty()

    def add_relationship(self):
        """Add a new relationship to the current entry."""
        rel_name = self.relationship_combo.currentText()
        rel_type = self.relationship_type.text().strip()
        if rel_name and rel_type and hasattr(self, 'current_entry'):
            rel_item = QTreeWidgetItem([rel_name, rel_type])
            self.relationships_list.addTopLevelItem(rel_item)
            self.relationship_type.clear()
            self.mark_dirty()

    def show_relationships_context_menu(self, pos):
        """Show context menu for relationships list."""
        item = self.relationships_list.itemAt(pos)
        if item:
            menu = QMenu(self)
            menu.addAction(_("Remove Relationship"), lambda: self.remove_relationship(item))
            menu.exec_(self.relationships_list.viewport().mapToGlobal(pos))

    def remove_relationship(self, item):
        """Remove a relationship from the relationships list."""
        index = self.relationships_list.indexOfTopLevelItem(item)
        self.relationships_list.takeTopLevelItem(index)
        self.mark_dirty()

    def add_image(self):
        """Add an image to the current entry."""
        file_name, _ = QFileDialog.getOpenFileName(self, _("Select Image"), "", _("Images (*.png *.jpg *.jpeg *.bmp)"))
        if file_name and hasattr(self, 'current_entry'):
            pixmap = QPixmap(file_name)
            if not pixmap.isNull():
                label = QLabel()
                label.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio))
                self.image_layout.addWidget(label)
                self.compendium_data["extensions"]["entries"][self.current_entry]["images"].append(file_name)
                self.mark_dirty()

    def load_images(self, images):
        """Load images into the images tab."""
        self.clear_images()
        for image_path in images:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                label = QLabel()
                label.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio))
                self.image_layout.addWidget(label)

    def get_images(self):
        """Return the list of image paths for the current entry."""
        if hasattr(self, 'current_entry'):
            return self.compendium_data["extensions"]["entries"].get(self.current_entry, {}).get("images", [])
        return []

    def update_entry_indicator(self):
        """Update the entry indicator based on relationships (green if has relationships)."""
        if hasattr(self, 'current_entry'):
            relationships = self.compendium_data["extensions"]["entries"].get(self.current_entry, {}).get("relationships", [])
            if relationships:
                self.entry_name_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: green;")
            else:
                self.entry_name_label.setStyleSheet("font-size: 16pt; font-weight: bold;")

    def on_compendium_updated(self, updated_project_name):
        """Handle compendium update notifications from the event bus."""
        if updated_project_name == self.project_name:
            self.populate_compendium()

    def filter_tree(self):
        """Filter the tree based on search bar input (entries and tags)."""
        search_text = self.search_bar.text().lower()
        for i in range(self.tree.topLevelItemCount()):
            cat_item = self.tree.topLevelItem(i)
            cat_visible = False
            for j in range(cat_item.childCount()):
                entry_item = cat_item.child(j)
                entry_name = entry_item.text(0).lower()
                entry_tags = self.compendium_data["extensions"]["entries"].get(entry_item.text(0), {}).get("tags", [])
                tag_names = [tag.get("name", "").lower() if isinstance(tag, dict) else tag.lower() for tag in entry_tags]
                entry_visible = search_text in entry_name or any(search_text in tag for tag in tag_names)
                entry_item.setHidden(not entry_visible)
                if entry_visible:
                    cat_visible = True
            cat_item.setHidden(not cat_visible)