from PyQt5.QtWidgets import QWidget, QSplitter, QTreeWidget, QTextEdit, QVBoxLayout, QMenu, QTreeWidgetItem, QMessageBox, QDialog
from PyQt5.QtCore import Qt, QPoint, pyqtSignal, pyqtSlot
import json, os, re
from langchain.prompts import PromptTemplate

from .enhanced_compendium import EnhancedCompendiumWindow
from .ai_compendium_dialog import AICompendiumDialog
from settings.llm_api_aggregator import WWApiAggregator
from settings.settings_manager import WWSettingsManager
from settings.llm_settings_dialog import LLMSettingsDialog

DEBUG = False  # Set to True to enable debug prints

def sanitize(text):
    return re.sub(r'\W+', '', text)

class CompendiumPanel(QWidget):
        # Optional signal if ContextPanel itself updates the compendium in the future
    compendium_updated = pyqtSignal(str)  # str is the project_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.project_window = parent

        # Determine the project name from the parent window and set the compendium file path.
        self.project_name = getattr(self.parent().model, "project_name", "default")
        self.new_compendium_file = os.path.join(os.getcwd(), "Projects", sanitize(self.project_name), "compendium.json")
        if DEBUG:
            print("New compendium file path:", self.new_compendium_file)
        
        # Ensure the project directory exists.
        project_dir = os.path.dirname(self.new_compendium_file)
        if not os.path.exists(project_dir):
            os.makedirs(project_dir)
        
        # Check for an old compendium file in the main directory.
        self.old_compendium_file = os.path.join(os.getcwd(), "compendium.json")
        if os.path.exists(self.old_compendium_file):
            if DEBUG:
                print("Old compendium file found at", self.old_compendium_file)
            try:
                with open(self.old_compendium_file, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                # Save data to the new compendium file.
                with open(self.new_compendium_file, "w", encoding="utf-8") as f:
                    json.dump(old_data, f, indent=2)
                # Delete the old compendium file.
                os.remove(self.old_compendium_file)
                if DEBUG:
                    print("Migrated compendium data to", self.new_compendium_file)
            except Exception as e:
                if DEBUG:
                    print("Error migrating old compendium file:", e)
        
        # Set self.compendium_file to the new location.
        self.compendium_file = self.new_compendium_file
        self.connect_to_compendium_signal()
        self.init_ui()

    def init_ui(self):
        # Create a horizontal splitter dividing the panel into a tree and an editor.
        self.splitter = QSplitter(Qt.Horizontal, self)
        
        # Left side: Tree for categories and entries.
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel(_("Compendium"))
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_tree_context_menu)
        self.tree.currentItemChanged.connect(self.on_item_changed)
        
        # Right side: Editor for the selected entry.
        # The editor is now set to read-only so that this panel serves only as a reference.
        self.editor = QTextEdit()
        self.editor.setPlaceholderText(_("Select a compendium entry to view."))
        self.editor.setReadOnly(True)
        
        # Set up the layout.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.splitter)
        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(self.editor)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        
        # Load the compendium data.
        self.populate_compendium()

    def populate_compendium(self):
        """Load compendium data from the file and populate the tree view."""
        # Capture current selection
        selected_item_info = self.get_selected_item_info()

        self.tree.clear()
        if os.path.exists(self.compendium_file):
            try:
                with open(self.compendium_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if DEBUG:
                    print("Compendium data loaded:", data)
                
                # Convert from old format if necessary.
                if isinstance(data.get("categories"), dict):
                    if DEBUG:
                        print("Old format detected. Converting data...")
                    old_categories = data["categories"]
                    category_order = data.get("category_order", list(old_categories.keys()))
                    new_categories = []
                    for cat_name in category_order:
                        entries_dict = old_categories.get(cat_name, {})
                        entries_list = []
                        for entry_name, entry_content in entries_dict.items():
                            entries_list.append({
                                "name": entry_name,
                                "content": entry_content
                            })
                        new_categories.append({
                            "name": cat_name,
                            "entries": entries_list
                        })
                    data["categories"] = new_categories
                    with open(self.compendium_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    if DEBUG:
                        print("Conversion complete. Data saved in new format.")
                
                # Populate the tree.
                for cat in data.get("categories", []):
                    cat_item = QTreeWidgetItem(self.tree, [cat.get("name", "Unnamed Category")])
                    cat_item.setData(0, Qt.UserRole, "category")
                    for entry in cat.get("entries", []):
                        entry_item = QTreeWidgetItem(cat_item, [entry.get("name", "Unnamed Entry")])
                        entry_item.setData(0, Qt.UserRole, "entry")
                        entry_item.setData(1, Qt.UserRole, entry.get("content", ""))
                    cat_item.setExpanded(True)
            except Exception as e:
                if DEBUG:
                    print("Error loading compendium data:", e)
        else:
            if DEBUG:
                print("Compendium file not found at", self.compendium_file)
            # Create default structure.
            default_data = {"categories": [{"name": "Characters", "entries": [{"name": "Readme", "content": "This is a dummy entry. You can view it for reference."}]}]}
            try:
                with open(self.compendium_file, "w", encoding="utf-8") as f:
                    json.dump(default_data, f, indent=2)
                if DEBUG:
                    print("Created default compendium data at", self.compendium_file)
            except Exception as e:
                if DEBUG:
                    print("Error creating default compendium file:", e)
            self.populate_compendium()

        # Restore selection
        self.restore_selection(selected_item_info)

    def get_selected_item_info(self):
        """Capture details of the currently selected item."""
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
        """Attempt to reselect the previously selected item."""
        if not selected_item_info:
            return
        item_type = selected_item_info["type"]
        item_name = selected_item_info["name"]

        if item_type == "category":
            # Search for category by name
            for i in range(self.tree.topLevelItemCount()):
                cat_item = self.tree.topLevelItem(i)
                if cat_item.text(0) == item_name and cat_item.data(0, Qt.UserRole) == "category":
                    self.tree.setCurrentItem(cat_item)
                    return
        elif item_type == "entry":
            # Search for entry in the specified category
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
            # If exact entry not found, try to find in the same category (handles renaming)
            if category_name:
                for i in range(self.tree.topLevelItemCount()):
                    cat_item = self.tree.topLevelItem(i)
                    if cat_item.text(0) == category_name:
                        if cat_item.childCount() > 0:
                            self.tree.setCurrentItem(cat_item.child(0))  # Select first entry
                        else:
                            self.tree.setCurrentItem(cat_item)  # Select category
                        return
        # If item not found, clear selection
        self.tree.clearSelection()


    def on_item_changed(self, current, previous):
        """Display entry content in the read-only editor when a tree item is selected."""
        if current is None:
            self.editor.clear()
            return
        if current.data(0, Qt.UserRole) == "entry":
            content = current.data(1, Qt.UserRole)
            self.editor.setPlainText(content)
        else:
            self.editor.clear()

    def show_tree_context_menu(self, pos: QPoint):
        """Display a simplified context menu with only the option to open the enhanced compendium."""
        menu = QMenu(self)
        action_open = menu.addAction(_("Open Enhanced Compendium"))
        action_analyze = menu.addAction(_("Analyze Scene with AI"))
        action = menu.exec_(self.tree.viewport().mapToGlobal(pos))

        if action == action_open:
            self.open_in_enhanced_compendium()
        elif action == action_analyze:
            self.analyze_scene_with_ai()

    def open_in_enhanced_compendium(self):
        """Launch the enhanced compendium window.
        If an entry is selected, the enhanced window will jump to that entry."""
        entry_name = None
        current_item = self.tree.currentItem()
        if current_item and current_item.data(0, Qt.UserRole) == "entry":
            entry_name = current_item.text(0)
            if entry_name.startswith("* "):
                entry_name = entry_name[2:]
        self.project_window.enhanced_window.open_with_entry(self.project_name, entry_name)

    def analyze_scene_with_ai(self):
        """Analyze current scene content and compendium using AI and show results."""
        # Get the scene editor content from the parent window
        scene_editor = self.project_window.scene_editor.editor
        if not scene_editor or not scene_editor.toPlainText():
            QMessageBox.warning(self, _("Warning"), _("No scene content available to analyze."))
            return

        scene_content = scene_editor.toPlainText()
        
        # Get existing compendium data
        current_compendium = {}
        if os.path.exists(self.compendium_file):
            try:
                with open(self.compendium_file, "r", encoding="utf-8") as f:
                    current_compendium = json.load(f)
            except Exception as e:
                print(f"Error loading compendium: {e}")

        overrides = LLMSettingsDialog.show_dialog(
            self,
            default_provider=WWSettingsManager.get_active_llm_name(),
            default_model=WWSettingsManager.get_active_llm_config().get("model", None),
            default_timeout=60
        )
        if not overrides:
            return  # User canceled

        # Define the PromptTemplate
        analysis_template = PromptTemplate(
            input_variables=["scene_content", "existing_compendium"],
            template="""Analyze the following scene content and existing compendium data. 
Generate or update compendium entries in JSON format for:
1. Major and minor characters (name, personality, description, relationships)
2. Locations (name, description)
3. Key objects (name, description)
4. Significant plot items (name, description)

Compendium entries apply to the entire story, so do not update existing entries for current status.

Scene Content:
{scene_content}

Existing Compendium:
{existing_compendium}

Return only the JSON result without additional commentary. The JSON should maintain the structure:
{{
  "categories": [
    {{
      "name": "category_name",
      "entries": [
        {{
          "name": "entry_name",
          "content": "description and details",
          "relationships": [{{"name": "related_entry", "type": "relationship_type"}}] (optional)
        }}
      ]
    }}
  ]
}}
"""
        )

        # Format the prompt using the template
        prompt = analysis_template.format(
            scene_content=scene_content,
            existing_compendium=json.dumps(current_compendium, indent=2)
        )

        try:
            # Use WWApiAggregator to get AI response
            response = WWApiAggregator.send_prompt_to_llm(prompt, overrides=overrides)
            
            # Preprocess to remove Markdown markers
            cleaned_response = self.preprocess_json_string(response)

            # Attempt to repair incomplete JSON
            repaired_response = self.repair_incomplete_json(cleaned_response)
            if repaired_response is None:
                QMessageBox.warning(self, _("Error"), _("AI returned invalid JSON that could not be repaired."))
                return
            
            # Validate JSON response
            try:
                ai_compendium = json.loads(repaired_response)
            except json.JSONDecodeError:
                QMessageBox.warning(self, _("Error"), _("AI returned invalid JSON format."))
                return

            # Show the dialog with AI results
            dialog = AICompendiumDialog(ai_compendium, self.compendium_file, self)
            if dialog.exec_() == QDialog.Accepted:
                self.save_ai_analysis(dialog.get_compendium_data())

        except Exception as e:
            QMessageBox.warning(self, _("Error"), _("Failed to analyze scene: {}").format(str(e)))

    def preprocess_json_string(self, raw_string):
        """Remove Markdown code block markers and extraneous whitespace from the string."""
        # Remove ```json (with optional language specifier) and ``` markers
        cleaned = re.sub(r'^```(?:json)?\s*\n', '', raw_string, flags=re.MULTILINE)
        cleaned = re.sub(r'\n```$', '', cleaned, flags=re.MULTILINE)
        # Remove leading/trailing whitespace
        return cleaned.strip()
    
    def repair_incomplete_json(self, json_str):
        """Attempt to repair incomplete JSON by adding missing closing brackets."""
        try:
            json.loads(json_str)  # If it parses, no repair needed
            return json_str
        except json.JSONDecodeError:
            # Add missing closing characters step-by-step
            repaired = json_str.strip()
            if repaired.endswith('"'):  # Ends with an open string
                repaired += '"'
            # Count and balance brackets
            open_braces = repaired.count('{') - repaired.count('}')
            open_brackets = repaired.count('[') - repaired.count(']')
            
            # Add missing closing braces and brackets
            for unusued in range(open_braces):
                repaired += '}'
            for unused in range(open_brackets):
                repaired += ']'
            
            try:
                json.loads(repaired)
                return repaired
            except json.JSONDecodeError:
                return None  # If still invalid, return None

    def save_ai_analysis(self, ai_compendium):
        """Save the AI-generated compendium analysis to the file."""
        try:
            # Merge with existing compendium if it exists
            if os.path.exists(self.compendium_file):
                with open(self.compendium_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                
                # Ensure extensions section exists
                if "extensions" not in existing:
                    existing["extensions"] = {"entries": {}}
                elif "entries" not in existing["extensions"]:
                    existing["extensions"]["entries"] = {}
        
                # Simple merge strategy: append new categories
                existing_categories = {cat["name"]: cat for cat in existing.get("categories", [])}
                for new_cat in ai_compendium.get("categories", []):
                    if new_cat["name"] in existing_categories:
                        existing_entries = {entry["name"]: entry for entry in existing_categories[new_cat["name"]]["entries"]}
                        for new_entry in new_cat.get("entries", []):
                            entry_name = new_entry["name"]
                            existing_entries[entry_name] = {
                                "name": entry_name,
                                "content": new_entry.get("content", ""),
                                "relationships": new_entry.get("relationships", [])
                            }
                            # Update extensions for EnhancedCompendiumWindow
                            existing["extensions"]["entries"][entry_name] = {
                                "relationships": new_entry.get("relationships", []),
                                **existing["extensions"]["entries"].get(entry_name, {})
                            }
                        existing_categories[new_cat["name"]]["entries"] = list(existing_entries.values())
                    else:
                        existing["categories"].append(new_cat)
                        # Add extensions for new entries
                        for entry in new_cat.get("entries", []):
                            entry_name = entry["name"]
                            existing["extensions"]["entries"][entry_name] = {
                                "relationships": entry.get("relationships", [])
                            }
            else:
                existing = {
                    "categories": ai_compendium.get("categories", []),
                    "extensions": {
                        "entries": {
                            entry["name"]: {"relationships": entry.get("relationships", [])}
                            for cat in ai_compendium.get("categories", [])
                            for entry in cat.get("entries", [])
                        }
                    }
                }

            # Save the merged compendium
            with open(self.compendium_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
            
            # Refresh the tree view
            self.populate_compendium()

            # Emit signal to notify EnhancedCompendiumWindow
            self.compendium_updated.emit(self.project_name)
            
            QMessageBox.information(self, _("Success"), _("Compendium updated successfully."))

        except Exception as e:
            QMessageBox.warning(self, _("Error"), _("Failed to save compendium: {}").format(str(e)))


    def connect_to_compendium_signal(self):
        """Connect to the EnhancedCompendiumWindow's compendium_updated signal."""
        # Traverse up to ProjectWindow to find EnhancedCompendiumWindow
        current_parent = self.parent()
        while current_parent:
            if hasattr(current_parent, 'enhanced_window') and isinstance(current_parent.enhanced_window, EnhancedCompendiumWindow):
                current_parent.enhanced_window.compendium_updated.connect(self.update_compendium_tree)
                break
            current_parent = current_parent.parent()
        
        # If not found (e.g., EnhancedCompendiumWindow not open yet), we'll try again later
        # Alternatively, we could connect when EnhancedCompendiumWindow is opened (see below)
        
    @pyqtSlot(str)
    def update_compendium_tree(self, project_name):
        """Update the compendium tree if the project name matches."""
        if project_name == self.project_name and self.isVisible():
            self.populate_compendium()