from PyQt5.QtWidgets import QMessageBox, QDialog, QAction, QMenu
from .rewrite_feature import RewriteDialog
from settings.settings_manager import WWSettingsManager
from settings.llm_api_aggregator import WWApiAggregator

class RightButtonMixin:
    def show_editor_context_menu(self, pos):
        """Create and show the custom context menu for the editor with LLM synonyms and rewrite functionality."""
        active_provider = WWSettingsManager.get_active_llm_name()
        config = WWSettingsManager.get_llm_config(active_provider)
        api_key_exists = bool(config and config.get("api_key"))
        
        menu = self.scene_editor.editor.createStandardContextMenu()
        cursor = self.scene_editor.editor.textCursor()
        
        if cursor.hasSelection():
            # Add 'Synonyms (LLM)' action available when text is selected
            synonyms_action = menu.addAction("Synonyms (LLM)")
            synonyms_action.triggered.connect(lambda: self.show_llm_synonyms_menu(cursor.selectedText().lower(), pos))
            
            # Only add 'Rewrite' action if an API key exists
            if api_key_exists:
                menu.addSeparator()
                rewrite_action = menu.addAction("Rewrite")
                rewrite_action.triggered.connect(self.rewrite_selected_text)
        
        menu.exec_(self.scene_editor.editor.mapToGlobal(pos))
    
    def rewrite_selected_text(self):
        cursor = self.scene_editor.editor.textCursor()
        if not cursor.hasSelection():
            QMessageBox.warning(self, "Rewrite", "No text selected to rewrite.")
            return
        selected_text = cursor.selectedText()
        dialog = RewriteDialog(self.model.project_name, selected_text, self)
        if dialog.exec_() == QDialog.Accepted:
            cursor.insertText(dialog.rewritten_text)
            self.scene_editor.editor.setTextCursor(cursor)
            
    def show_llm_synonyms_menu(self, word, pos):
        prompt = (
            f"Provide exactly 20 synonyms for '{word}', separated by commas. "
            "Your answer must consist only of the synonyms themselves, with no numbering or additional information. "
            "Do not translate the words into another language. Don't repeat synonyms. "
            "Do not add any extra punctuation, such as a period, at the end of the list of synonyms. "
            "Example: syn1, syn2, syn3, syn4, syn5, syn6, syn7, syn8, syn9, syn10, syn11, syn12, syn13, syn14, syn15, syn16, syn17, syn18, syn19, syn20"
        )
        try:
            response = WWApiAggregator.send_prompt_to_llm(prompt)
            # Split the response by commas and remove any extra whitespace
            synonyms = [syn.strip() for syn in response.split(',') if syn.strip()]
        
            menu = QMenu(self.scene_editor.editor)
            for syn in synonyms:
                action = QAction(syn, self)
                action.triggered.connect(lambda _, rep=syn: self.replace_selected_text(rep))
                menu.addAction(action)
        
            if not menu.actions():
                self.show_message("No synonyms found for this word.")
            else:
                menu.exec_(self.scene_editor.editor.mapToGlobal(pos))
        except Exception as e:
            self.show_message(f"Error while retrieving synonyms from LLM: {e}")

    def replace_selected_text(self, replacement):
        """Replaces the selected text in the editor with the given replacement."""
        cursor = self.scene_editor.editor.textCursor()
        if cursor.hasSelection():
            cursor.insertText(replacement)

    def show_message(self, message):
        print(message)  # Placeholder - replace with your GUI's message display
