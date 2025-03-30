import os, re
import json
import tiktoken
from PyQt5.QtWidgets import QMessageBox, QInputDialog, QApplication, QTextEdit
from PyQt5.QtCore import Qt
from settings.llm_worker import LLMWorker
from settings.settings_manager import WWSettingsManager


class SummaryCreator:
    """A class to handle the creation and management of summaries for a project."""

    def __init__(self, project_window, max_tokens=16000, encoding_name="cl100k_base"):
        """
        Initialize the SummaryCreator with a reference to the ProjectWindow.

        Args:
            project_window (ProjectWindow): The main project window instance.
        """
        self.project_window = project_window
        self.max_tokens = max_tokens
        self.encoding = tiktoken.get_encoding(encoding_name)

    def create_summary(self):
        """
        Create a summary for the selected Act or Chapter in the project tree.
        If no LLM API key is available, the summary feature is disabled.
        """
        # Check if LLM API key is configured
        if not self.project_window.llm_available:
            self._show_warning("LLM API key not configured. Summary feature is disabled.")
            return

        current_item = self._get_current_tree_item()
        if not self._validate_selection(current_item):
            return

        summary_prompts = self._load_summary_prompts()
        if not summary_prompts:
            self._show_warning("No summary prompts found. Please check your prompt options.")
            return

        selected_prompt = self._prompt_user_for_selection(summary_prompts)
        if not selected_prompt:
            return

        child_content = self._gather_child_content(current_item)
        if not child_content.strip():
            self._show_warning("No child scene content found to summarize.")
            return

        plain_text = self._html_to_optimized_plaintext(child_content)
        final_prompt = self._build_final_prompt(selected_prompt, plain_text)
        self._process_summary_generation(selected_prompt, final_prompt, current_item)

    def _html_to_optimized_plaintext(self, html_content):
        """
        Convert HTML to plain text optimized for minimal LLM tokens.

        Args:
            html_content (str): HTML content from child nodes.

        Returns:
            str: Preprocessed plain text.
        """
        # Convert HTML to plain text using QTextEdit's toPlainText
        temp_editor = QTextEdit()
        temp_editor.setHtml(html_content)
        text = temp_editor.toPlainText()

        # Preprocess to reduce tokens
        # 1. Normalize whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        # 2. Optionally remove stopwords (uncomment if using NLTK)
        # words = text.split()
        # text = ' '.join(word for word in words if word.lower() not in self.stop_words)
        # 3. Simplify punctuation
        text = re.sub(r'[.!?]+', '. ', text)  # Normalize sentence endings
        text = re.sub(r'[^a-zA-Z0-9\s.]', '', text)  # Remove special chars except periods

        # Check token count (approximate: 1 word ≈ 1.3 tokens)
        tokens = self.encoding.encode(text)
        if len(tokens) > self.max_tokens:
            return self._chunk_and_summarize(text, len(tokens))
        return text

    def _chunk_and_summarize(self, text, token_count):
        """
        Split large text into chunks and pre-summarize to fit token limits.

        Args:
            text (str): The plain text to chunk.
            token_count (int): Current token count.

        Returns:
            str: A condensed version of the text.
        """
        sentences = re.split(r'(?<=[.!?])\s+', text)
        target_tokens = self.max_tokens * 0.9  # Leave 10% buffer for prompt
        trimmed_text = []
        current_tokens = 0
        
        # Add sentences until token limit is approached
        for sentence in sentences:
            sentence_tokens = self.encoding.encode(sentence)
            if current_tokens + len(sentence_tokens) <= target_tokens:
                trimmed_text.append(sentence)
                current_tokens += len(sentence_tokens)
            else:
                break

        result = ' '.join(trimmed_text)
        final_tokens = self.encoding.encode(result)
        if len(final_tokens) > self.max_tokens:
            # Last resort: truncate to exact token limit
            result = self.encoding.decode(final_tokens[:int(self.max_tokens)])
        return result

    def _get_current_tree_item(self):
        """Retrieve the currently selected item in the project tree."""
        return self.project_window.project_tree.tree.currentItem()

    def _validate_selection(self, item):
        """Validate that an Act or Chapter is selected."""
        if not item or self._get_tree_level(item) >= 2:
            self._show_warning("Please select an Act or Chapter (not a Scene).")
            return False
        return True

    def _get_tree_level(self, item):
        """
        Determine the tree level of the given item (0 for Act, 1 for Chapter, 2+ for Scene).

        Args:
            item: The QTreeWidgetItem to check.

        Returns:
            int: The level of the item in the tree.
        """
        level = 0
        temp = item
        while temp.parent():
            level += 1
            temp = temp.parent()
        return level

    def _load_summary_prompts(self):
        """
        Load summary prompts from the project's prompts JSON file.

        Returns:
            list: A list of summary prompt dictionaries, or an empty list if loading fails.
        """
        prompts_file = WWSettingsManager.get_project_path(file="prompts.json")
        if not os.path.exists(prompts_file):
            return []

        try:
            with open(prompts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("Summary", [])
        except Exception as e:
            print(f"Error loading summary prompts: {e}")
            return []

    def _prompt_user_for_selection(self, summary_prompts):
        """
        Prompt the user to select a summary prompt from the available options.

        Args:
            summary_prompts (list): List of summary prompt dictionaries.

        Returns:
            dict: The selected prompt dictionary, or None if selection is canceled or invalid.
        """
        prompt_names = [p.get("name", "Unnamed") for p in summary_prompts]
        selected, ok = QInputDialog.getItem(
            self.project_window,
            "Select Summary Prompt",
            "Choose a summary prompt for summarization:",
            prompt_names,
            0,
            False
        )
        if not ok or not selected:
            return None

        return next(p for p in summary_prompts if p.get("name", "Unnamed") == selected)

    def _gather_child_content(self, item):
        """
        Recursively gather text content from all leaf nodes (scenes) under the given item.

        Args:
            item: The QTreeWidgetItem to gather content from.

        Returns:
            str: The concatenated content from all child scenes.
        """
        content = ""
        if item.childCount() == 0:
            data = item.data(0, Qt.UserRole)
            if data:
                text = (data.get("content", "") if isinstance(data, dict) else data) or data.get("summary", "")
                content += text + "\n"
        else:
            for i in range(item.childCount()):
                child = item.child(i)
                content += self._gather_child_content(child)
        return content

    def _build_final_prompt(self, prompt, content):
        """
        Build the final prompt by combining the selected prompt and gathered content.

        Args:
            prompt (dict): The selected summary prompt dictionary.
            content (str): The gathered child content.

        Returns:
            str: The final prompt string for the LLM.
        """
        return f"### User {prompt.get('text')}\n\nContent:\n{content}"

    def _process_summary_generation(self, prompt, final_prompt, current_item):
        """
        Send the final prompt to the LLM and handle the summary generation process.

        Args:
            final_prompt (str): The prompt to send to the LLM.
            current_item: The QTreeWidgetItem being summarized.
        """
        self.project_window.statusBar().showMessage("Generating summary, please wait...", 5000)
        QApplication.processEvents()  # Update UI

        self.worker = LLMWorker(final_prompt, self._get_llm_overrides(prompt))
        self.worker.data_received.connect(self._on_summary_update)
        self.worker.finished.connect(lambda: self._on_summary_ready(current_item))
        self.project_window.scene_editor.editor.clear()
        self.worker.start()

    def _on_summary_update(self, text):
        self.project_window.scene_editor.editor.insertPlainText(text)

    def _get_llm_overrides(self, prompt):
        """
        Provide default LLM configuration overrides.

        Returns:
            dict: Configuration overrides for the LLMWorker.
        """
        return {
            "provider": prompt.get("provider", ""),
            "model": prompt.get("model", ""),
            "max_tokens": prompt.get("max_tokens", 2000),
            "temperature": prompt.get("temperature", 1.0)
        }

    def _on_summary_ready(self, current_item):
        """
        Handle the completion of summary generation, displaying and saving the result.

        Args:
            current_item: The QTreeWidgetItem being summarized.
        """
        generated_summary = self.project_window.scene_editor.editor.toPlainText()
        if not generated_summary:
            self._show_warning("LLM returned no output.")
            return

        # Save to project structure - user can still edit it and manual save
        itemdata = current_item.data(0, Qt.UserRole)
        itemdata["summary"] = generated_summary
        current_item.setData(0, Qt.UserRole, itemdata)
        self.project_window.model.update_structure(self.project_window.project_tree.tree)

        self._save_summary_to_file(generated_summary, current_item)

    def _save_summary_to_file(self, summary, item):
        """
        Save the generated summary to a file.

        Args:
            summary (str): The generated summary text.
            item: The QTreeWidgetItem associated with the summary.
        """
        filename = self._generate_default_filename(item)

        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(summary)
            self._show_info(f"Summary created and saved to {filename}.")
        except Exception as e:
            self._show_warning(f"Could not save summary: {e}")

    def _generate_default_filename(self, item):
        """
        Generate a default filename if get_summary_filename is not available.

        Args:
            item: The QTreeWidgetItem to generate a filename for.

        Returns:
            str: The generated file path.
        """
        hierarchy = []
        temp = item
        while temp:
            hierarchy.insert(0, temp.text(0).strip())
            temp = temp.parent()

        project_name = self.project_window.model.project_name
        sanitized = [WWSettingsManager.sanitize(x) for x in hierarchy]
        filename = f"{project_name}-Summary-{'-'.join(sanitized)}.txt"
        return WWSettingsManager.get_project_path(project_name, filename)

    def _show_warning(self, message):
        """Display a warning message to the user."""
        QMessageBox.warning(self.project_window, "Summary", message)

    def _show_info(self, message):
        """Display an informational message to the user."""
        QMessageBox.information(self.project_window, "Summary", message)


# Example usage (if this were a standalone script)
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    from project_window import ProjectWindow  # Assuming this is available

    app = QApplication(sys.argv)
    window = ProjectWindow("TestProject")
    summary_creator = SummaryCreator(window)
    summary_creator.create_summary()
    sys.exit(app.exec_())
