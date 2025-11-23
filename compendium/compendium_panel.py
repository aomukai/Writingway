from PyQt5.QtWidgets import QWidget, QTreeWidget, QVBoxLayout, QMenu, QTreeWidgetItem, QMessageBox, QDialog
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QFont, QBrush
import json, os, re, uuid
from langchain.prompts import PromptTemplate
from .ai_compendium_dialog import AICompendiumDialog
from settings.llm_api_aggregator import WWApiAggregator
from settings.settings_manager import WWSettingsManager
from settings.theme_manager import ThemeManager
from settings.llm_settings_dialog import LLMSettingsDialog
from compendium.compendium_manager import CompendiumManager, CompendiumEventBus

DEBUG = False

def sanitize(text):
    return re.sub(r'\W+', '', text)

class CompendiumPanel(QWidget):
    def __init__(self, parent=None, enhanced_window=None):
        super().__init__(parent)
        self.setMinimumWidth(300)
        self.project_window = parent
        self.enhanced_window = enhanced_window
        self.project_name = getattr(self.parent().model, "project_name", "default")
        self.event_bus = CompendiumEventBus.get_instance()
        self.manager = CompendiumManager(self.project_name, event_bus=self.event_bus)
        self.event_bus.add_updated_listener(self.update_compendium_tree)
        self.compendium_file = os.path.join(os.getcwd(), "Projects", sanitize(self.project_name), "compendium.json")
        if DEBUG:
            print("New compendium file path:", self.compendium_file)

        project_dir = os.path.dirname(self.compendium_file)
        if not os.path.exists(project_dir):
            os.makedirs(project_dir)

        self.old_compendium_file = os.path.join(os.getcwd(), "compendium.json")
        if os.path.exists(self.old_compendium_file):
            if DEBUG:
                print("Old compendium file found at", self.old_compendium_file)
            try:
                with open(self.old_compendium_file, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                self.manager.save_data(old_data)
                os.remove(self.old_compendium_file)
                if DEBUG:
                    print("Migrated compendium data to", self.compendium_file)
            except Exception as e:
                if DEBUG:
                    print("Error migrating old compendium file:", e)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel(_("Compendium"))
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_tree_context_menu)
        self.tree.currentItemChanged.connect(self.on_item_changed)
        layout.addWidget(self.tree)
        self.populate_compendium()

    def populate_compendium(self):
        selected_item_info = self.get_selected_item_info()
        self.tree.clear()
        bold_font = QFont()
        bold_font.setBold(True)
        data = self.manager.load_data()
        if DEBUG:
            print("Compendium data loaded:", data)

        for cat in data.get("categories", []):
            cat_item = QTreeWidgetItem(self.tree, [cat.get("name", "Unnamed Category")])
            cat_item.setData(0, Qt.UserRole, "category")
            cat_item.setData(0, Qt.ItemDataRole.UserRole + 1, "true")
            cat_item.setBackground(0, QBrush(ThemeManager.get_category_background_color()))
            cat_item.setFont(0, bold_font)
            for entry in sorted(cat.get("entries", []), key=lambda e: e.get("name", "")):
                entry_item = QTreeWidgetItem(cat_item, [entry.get("name", "Unnamed Entry")])
                entry_item.setData(0, Qt.UserRole, "entry")
                entry_item.setData(1, Qt.UserRole, entry.get("content", ""))
                entry_item.setData(2, Qt.UserRole, entry.get("uuid", str(uuid.uuid4())))
            cat_item.setExpanded(True)
        self.restore_selection(selected_item_info)

    def get_selected_item_info(self):
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

    def on_item_changed(self, current, previous):
        """Display entry content in the main editor."""
        main_editor = self.project_window.compendium_editor
        if current is None:
            main_editor.clear()
            return
        if current.data(0, Qt.UserRole) == "entry":
            content = current.data(1, Qt.UserRole)
            main_editor.setPlainText(content)
        else:
            main_editor.clear()

    def show_tree_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        action_open = menu.addAction(_("Open Enhanced Compendium"))
        action_analyze = menu.addAction(_("Analyze Scene with AI"))
        action = menu.exec_(self.tree.viewport().mapToGlobal(pos))
        if action == action_open:
            self.open_in_enhanced_compendium()
        elif action == action_analyze:
            self.analyze_scene_with_ai()

    def open_in_enhanced_compendium(self):
        if not self.enhanced_window:
            QMessageBox.warning(self, _("Error"), _("Enhanced Compendium window not available."))
            return
        entry_name = None
        current_item = self.tree.currentItem()
        if current_item and current_item.data(0, Qt.UserRole) == "entry":
            entry_name = current_item.text(0)
            if entry_name.startswith("* "):
                entry_name = entry_name[2:]
        self.enhanced_window.open_with_entry(self.project_name, entry_name)

    def analyze_scene_with_ai(self):
        scene_editor = self.project_window.scene_editor.editor
        if not scene_editor or not scene_editor.toPlainText():
            QMessageBox.warning(self, _("Warning"), _("No scene content available to analyze."))
            return
        scene_content = scene_editor.toPlainText()
        current_compendium = self.manager.load_data()
        overrides = LLMSettingsDialog.show_dialog(
            self,
            default_provider=WWSettingsManager.get_active_llm_name(),
            default_model=WWSettingsManager.get_active_llm_config().get("model", None),
            default_timeout=60
        )
        if not overrides:
            return
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
        prompt = analysis_template.format(
            scene_content=scene_content,
            existing_compendium=json.dumps(current_compendium, indent=2)
        )
        try:
            response = WWApiAggregator.send_prompt_to_llm(prompt, overrides=overrides)
            cleaned_response = self.preprocess_json_string(response)
            repaired_response = self.repair_incomplete_json(cleaned_response)
            if repaired_response is None:
                QMessageBox.warning(self, _("Error"), _("AI returned invalid JSON that could not be repaired."))
                return
            try:
                ai_compendium = json.loads(repaired_response)
            except json.JSONDecodeError:
                QMessageBox.warning(self, _("Error"), _("AI returned invalid JSON format."))
                return
            dialog = AICompendiumDialog(ai_compendium, self.compendium_file, self)
            if dialog.exec_() == QDialog.Accepted:
                self.save_ai_analysis(dialog.get_compendium_data())
        except Exception as e:
            QMessageBox.warning(self, _("Error"), _("Failed to analyze scene: {}").format(str(e)))

    def preprocess_json_string(self, raw_string):
        cleaned = re.sub(r'^```(?:json)?\s*\n', '', raw_string, flags=re.MULTILINE)
        cleaned = re.sub(r'\n```$', '', cleaned, flags=re.MULTILINE)
        return cleaned.strip()

    def repair_incomplete_json(self, json_str):
        try:
            json.loads(json_str)
            return json_str
        except json.JSONDecodeError:
            repaired = json_str.strip()
            if repaired.endswith('"'):
                repaired += '"'
            open_braces = repaired.count('{') - repaired.count('}')
            open_brackets = repaired.count('[') - repaired.count(']')
            for _ in range(open_braces):
                repaired += '}'
            for _ in range(open_brackets):
                repaired += ']'
            try:
                json.loads(repaired)
                return repaired
            except json.JSONDecodeError:
                return None

    def save_ai_analysis(self, ai_compendium):
        try:
            ai_compendium.setdefault("extensions", {"entries": {}})
            for cat in ai_compendium.get("categories", []):
                for entry in cat.get("entries", []):
                    entry_name = entry.get("name")
                    if entry_name:
                        entry.setdefault("uuid", str(uuid.uuid4()))
                        ai_compendium["extensions"]["entries"][entry_name] = {
                            "relationships": entry.get("relationships", []),
                            "details": "",
                            "tags": [],
                            "images": []
                        }
            self.manager.upsert_data(ai_compendium)
            self.populate_compendium()
            QMessageBox.information(self, _("Success"), _("Compendium updated successfully."))
        except Exception as e:
            QMessageBox.warning(self, _("Error"), _("Failed to save compendium: {}").format(str(e)))

    def update_compendium_tree(self, project_name):
        if project_name == self.project_name and self.isVisible():
            self.populate_compendium()