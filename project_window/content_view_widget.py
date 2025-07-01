from PyQt5.QtWidgets import (
    QWidget, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QTextEdit, QHBoxLayout, QLabel, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal

class ContentViewWidget(QWidget):
    """Content View with tabs, showing Acts, Chapters, Scenes with editable content and summary."""

    # Signal to notify ProjectWindow to save changes
    content_changed = pyqtSignal(list, str, str)  # hierarchy, content_type ('scene' or 'summary'), new_text

    def __init__(self, project_model, parent=None):
        super().__init__(parent)
        self.project_model = project_model

        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # First tab: Acts with nested Chapters and Scenes
        self.act_tab = QWidget()
        self.tabs.addTab(self.act_tab, "Content View")

        act_layout = QVBoxLayout(self.act_tab)

        # Use splitter to separate tree and editor area
        self.splitter = QSplitter(Qt.Horizontal)
        act_layout.addWidget(self.splitter)

        # Left: Tree showing Act > Chapter > Scene
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Name", "Scene Content", "Scene Summary"])
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 300)
        self.tree.setColumnWidth(2, 300)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.tree.itemChanged.connect(self.on_item_changed)
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setEditTriggers(QTreeWidget.DoubleClicked | QTreeWidget.SelectedClicked | QTreeWidget.EditKeyPressed)

        self.splitter.addWidget(self.tree)

        # Right: Editor area for content and summary
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(0, 0, 0, 0)

        self.content_label = QLabel("Scene Content:")
        self.content_edit = QTextEdit()
        self.content_edit.textChanged.connect(self.on_content_edit_changed)

        self.summary_label = QLabel("Scene Summary:")
        self.summary_edit = QTextEdit()
        self.summary_edit.textChanged.connect(self.on_summary_edit_changed)

        editor_layout.addWidget(self.content_label)
        editor_layout.addWidget(self.content_edit)
        editor_layout.addWidget(self.summary_label)
        editor_layout.addWidget(self.summary_edit)

        self.splitter.addWidget(editor_widget)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        # Track current selected scene hierarchy
        self.current_hierarchy = None
        self.updating_text = False  # To avoid recursive signals

    def load_data(self):
        """Load Acts, Chapters, Scenes from project_model.structure into the tree."""
        self.tree.clear()
        acts = self.project_model.structure.get("acts", [])
        for act in acts:
            act_item = QTreeWidgetItem(self.tree, [act.get("name", "Unnamed Act")])
            act_item.setFlags(act_item.flags() & ~Qt.ItemIsEditable)  # Act name not editable here
            chapters = act.get("chapters", [])
            for chapter in chapters:
                chapter_item = QTreeWidgetItem(act_item, [chapter.get("name", "Unnamed Chapter")])
                chapter_item.setFlags(chapter_item.flags() & ~Qt.ItemIsEditable)  # Chapter name not editable here
                scenes = chapter.get("scenes", [])
                for scene in scenes:
                    scene_name = scene.get("name", "Unnamed Scene")
                    scene_item = QTreeWidgetItem(chapter_item, [scene_name, "", ""])
                    scene_item.setFlags(scene_item.flags() | Qt.ItemIsEditable)
                    # Load scene content and summary
                    hierarchy = [act.get("name"), chapter.get("name"), scene_name]
                    content = self.project_model.load_scene_content(hierarchy) or ""
                    summary = self.project_model.load_summary(hierarchy) or ""
                    scene_item.setText(1, content)
                    scene_item.setText(2, summary)
        self.tree.expandAll()

    def on_item_clicked(self, item, column):
        """When user clicks a scene row, load content and summary into editors."""
        if self.is_scene_item(item):
            hierarchy = self.get_hierarchy(item)
            self.current_hierarchy = hierarchy
            self.updating_text = True
            content = self.project_model.load_scene_content(hierarchy) or ""
            summary = self.project_model.load_summary(hierarchy) or ""
            self.content_edit.setPlainText(content)
            self.summary_edit.setPlainText(summary)
            self.updating_text = False
        else:
            self.current_hierarchy = None
            self.updating_text = True
            self.content_edit.clear()
            self.summary_edit.clear()
            self.updating_text = False

    def on_content_edit_changed(self):
        if self.updating_text or not self.current_hierarchy:
            return
        new_text = self.content_edit.toPlainText()
        self.content_changed.emit(self.current_hierarchy, "scene", new_text)

    def on_summary_edit_changed(self):
        if self.updating_text or not self.current_hierarchy:
            return
        new_text = self.summary_edit.toPlainText()
        self.content_changed.emit(self.current_hierarchy, "summary", new_text)

    def on_item_changed(self, item, column):
        """Allow editing scene name only."""
        if self.is_scene_item(item) and column == 0:
            new_name = item.text(0).strip()
            if not new_name:
                # Revert to old name if empty
                self.load_data()
                return
            old_hierarchy = self.get_hierarchy(item)
            old_name = old_hierarchy[-1]
            if new_name != old_name:
                # Rename scene in project model
                act_name = old_hierarchy[0]
                chapter_name = old_hierarchy[1]
                self.project_model.rename_node(old_hierarchy, new_name)
                # Reload data to reflect changes
                self.load_data()

    def is_scene_item(self, item):
        """Check if the item is a scene (level 2 in tree)."""
        return item and item.parent() and item.parent().parent() is not None

    def get_hierarchy(self, item):
        """Return [Act, Chapter, Scene] hierarchy for a scene item."""
        if not item:
            return None
        chapter_item = item.parent()
        act_item = chapter_item.parent() if chapter_item else None
        if act_item:
            return [act_item.text(0), chapter_item.text(0), item.text(0)]
        return None
