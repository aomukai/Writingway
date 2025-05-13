from PyQt5.QtCore import Qt
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox
from .summary_service import SummaryService
from muse.prompt_preview_dialog import PromptPreviewDialog

class SummaryController(QObject):
    status_updated = pyqtSignal(str)

    def __init__(self, model, view, project_tree):
        super().__init__()
        self.model = model
        self.view = view  # BottomStack instance
        self.project_tree = project_tree
        self.service = SummaryService()
        self.service.summary_generated.connect(self._update_editor)
        self.service.error_occurred.connect(self._show_error)

    def create_summary(self):
        current_item = self.project_tree.tree.currentItem()
        if not self._validate_selection(current_item):
            return

        prompt = self.view.summary_prompt_panel.get_prompt()
        if not prompt:
            self._show_warning(_("Selected prompt not found."))
            return
        overrides = self.view.summary_prompt_panel.get_overrides()

        child_content = self.model.gather_child_content(current_item)
        if not child_content.strip():
            self._show_warning(_("No child scene content found to summarize."))
            return

        plain_text = self.model.optimize_text(child_content)
        self.view.scene_editor.editor.clear()
        self.status_updated.emit(_("Generating summary, please wait..."))
        self.service.generate_summary(prompt, plain_text, overrides)
        self.current_item = current_item

    def preview_summary(self):
        """Handle preview button click to show the final prompt."""
        prompt = self.view.summary_prompt_panel.get_prompt()
        prompt_name = prompt.get("name", None)
        if not prompt_name or prompt_name == _("Select Summary Prompt"):
            self._show_warning(_("Please select a summary prompt."))
            return

        current_item = self.project_tree.tree.currentItem()
        if not self._validate_selection(current_item):
            return

        child_content = self.model.gather_child_content(current_item)
        if not child_content.strip():
            self._show_warning(_("No child scene content found to summarize."))
            return

        plain_text = self.model.optimize_text(child_content)
#        final_prompt = self.model.build_final_prompt(prompt, plain_text)

        # Show the preview dialog
        dialog = PromptPreviewDialog(
            controller=self.view.controller,
            prompt_config=prompt,
            user_input=None,  # No user input for summary preview
            additional_vars=None,  # No additional vars needed here
            current_scene_text=plain_text,
            extra_context=None
        )
        dialog.exec_()

    def _validate_selection(self, item):
        if not item or self.project_tree.get_item_level(item) >= 2:
            self._show_warning(_("Please select an Act or Chapter (not a Scene)."))
            return False
        return True

    def _update_editor(self, text):
        editor = self.view.scene_editor.editor
        editor.insertPlainText(text)

    def _on_summary_complete(self):
        generated_summary = self.view.scene_editor.editor.toPlainText()
        if not generated_summary:
            self._show_warning(_("LLM returned no output."))
            return
        item_data = self.current_item.data(0, Qt.UserRole) or {"name": self.current_item.text(0)}
        item_data["summary"] = generated_summary
        self.current_item.setData(0, Qt.UserRole, item_data)
        self.project_tree.model.update_structure(self.project_tree.tree)
        self.status_updated.emit(_("Summary generated successfully."))

    def _show_warning(self, message):
        QMessageBox.warning(self.view, _("Summary"), message)

    def _show_error(self, message):
        QMessageBox.critical(self.view, _("Summary Error"), message)
