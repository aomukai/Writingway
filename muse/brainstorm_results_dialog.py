from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QPushButton, QHBoxLayout, QTextEdit, QLabel
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QFont, QColor
from settings.theme_manager import ThemeManager
import muse.prompt_handler as prompt_handler

class BrainstormResultsDialog(QDialog):
    def __init__(self, results, judge_response, context_text, action_beats, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Brainstorm Results")
        self.resize(800, 600)
        self.results = results
        self.judge_response = judge_response
        self.context_text = context_text
        self.action_beats = action_beats
        self.init_ui()
        self.read_settings()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Tree widget for collapsible sections
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(2)  # Column 0 for header, Column 1 for content widget
        self.tree.setColumnWidth(0, 200)  # Fixed width for headers
        self.populate_tree()
        layout.addWidget(self.tree)

        # Buttons
        button_layout = QHBoxLayout()
        
        # Add Append to Scene button
        self.append_button = QPushButton("Append to Scene")
        self.append_button.clicked.connect(self.append_to_scene)
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)

        button_layout.addWidget(self.append_button)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        layout.addLayout(button_layout)

    def populate_tree(self):
        """Populate the tree with collapsible sections."""
        sections = {}
        
        # Add action beats section
        if self.action_beats:
            sections["Action Beats"] = self.action_beats
            
        # Add context section
        if self.context_text:
            sections["Context"] = self.context_text
            
        # Add individual responses
        for i, result in enumerate(self.results):
            header = f"Response {i+1} - {result['provider']} - {result['model']}"
            sections[header] = result['response']
            
        # Add judge response
        if self.judge_response:
            sections["Judge Evaluation"] = self.judge_response

        for header, content in sections.items():
            # Create a top-level item for the header
            header_item = QTreeWidgetItem(self.tree)
            header_item.setText(0, header)
            header_item.setFont(0, QFont("Arial", 12, QFont.Bold))

            # Create a child item to hold the QTextEdit
            content_item = QTreeWidgetItem(header_item)
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setPlainText(content)
            text_edit.setFont(QFont("Arial", 12))
            text_edit.setStyleSheet("QTextEdit { border: 1px solid #ccc; padding: 4px; }")  # Add boundary box
            self.tree.setItemWidget(content_item, 1, text_edit)

            # Collapse if content is long (>300 chars)
            if len(content.strip()) > 300:
                header_item.setExpanded(False)
            else:
                header_item.setExpanded(True)

        # Adjust tree after adding widgets
        self.tree.expandAll()  # Expand all initially, then collapse long sections
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item and item.childCount() > 0:
                child_item = item.child(0)
                text_edit = self.tree.itemWidget(child_item, 1)
                if text_edit:
                    content_length = len(text_edit.toPlainText().strip())
                    maxheight = min(max(2, int(content_length / 50)), 50) * 30
                    text_edit.setMaximumHeight(maxheight)  # Ensure visibility

                    if content_length > 300:
                        item.setExpanded(False)
            # Resize the content column to fit the widget
            self.tree.resizeColumnToContents(1)

    def append_to_scene(self):
        """Append the selected text to the main scene."""
        # Get the currently selected item
        current_item = self.tree.currentItem()
        if current_item:
            # Check if it's a content item (child of a header)
            parent = current_item.parent()
            if parent:
                # Get the text edit widget for this item
                text_edit = self.tree.itemWidget(current_item, 1)
                if text_edit:
                    # Get the text content
                    text_content = text_edit.toPlainText()
                    if text_content:
                        # Append to the main scene
                        parent_window = self.parent()
                        if parent_window:
                            # Set the text in the preview area and call apply_preview
                            # Try to find the bottom stack in the parent hierarchy
                            bottom_stack = getattr(parent_window, 'bottom_stack', None)
                            if bottom_stack and hasattr(bottom_stack, 'preview_text'):
                                bottom_stack.preview_text.setPlainText(text_content)
                                # Call the controller's apply_preview method
                                controller = getattr(bottom_stack, 'controller', None)
                                if controller and hasattr(controller, 'apply_preview'):
                                    controller.apply_preview()
                            else:
                                # If we can't find bottom_stack, try to find preview_text directly
                                preview_text = getattr(parent_window, 'preview_text', None)
                                if preview_text:
                                    preview_text.setPlainText(text_content)
                                    # Try to find the controller and call apply_preview
                                    controller = getattr(parent_window, 'controller', None)
                                    if controller and hasattr(controller, 'apply_preview'):
                                        controller.apply_preview()
                                else:
                                    # Last resort: try to find it in parent's attributes
                                    for attr_name in dir(parent_window):
                                        attr = getattr(parent_window, attr_name)
                                        if hasattr(attr, 'preview_text'):
                                            preview_text = getattr(attr, 'preview_text', None)
                                            if preview_text:
                                                preview_text.setPlainText(text_content)
                                                # Try to find the controller and call apply_preview
                                                controller = getattr(attr, 'controller', None)
                                                if controller and hasattr(controller, 'apply_preview'):
                                                    controller.apply_preview()
                                                break

    def read_settings(self):
        settings = QSettings("MyCompany", "WritingwayProject")
        geometry = settings.value("brainstorm_results/geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def write_settings(self):
        settings = QSettings("MyCompany", "WritingwayProject")
        settings.setValue("brainstorm_results/geometry", self.saveGeometry())

    def closeEvent(self, a0):
        self.write_settings()
        super().closeEvent(a0)