import re
import tiktoken
from PyQt5.QtCore import Qt

class SummaryModel:
    def __init__(self, project_name, max_tokens=16000, encoding_name="cl100k_base"):
        self.project_name = project_name
        self.max_tokens = max_tokens
        self.encoding = tiktoken.get_encoding(encoding_name)
        self.structure = None  # Set by controller

    def optimize_text(self, html_content):
        """Convert HTML to optimized plain text for LLM."""
        from PyQt5.QtWidgets import QTextEdit
        temp_editor = QTextEdit()
        temp_editor.setHtml(html_content)
        text = temp_editor.toPlainText()

        # Minimal whitespace normalization: collapse multiple newlines/spaces, but preserve word boundaries
        text = re.sub(r'\n+', '\n', text.strip())  # Collapse newlines
        text = re.sub(r'[ \t]+', ' ', text)  # Collapse spaces/tabs, but keep them
        
        tokens = self.encoding.encode(text)
        if len(tokens) > self.max_tokens:
            return self._chunk_text(text, tokens)
        return text

    def _chunk_text(self, text, tokens):
        """Chunk text to fit token limit."""
        target_tokens = int(self.max_tokens * 0.9)
        trimmed_text = []
        current_tokens = 0

        # Split by newlines first (paragraph-like boundaries)
        lines = text.split('\n')
        for line in lines:
            line_tokens = self.encoding.encode(line)
            if current_tokens + len(line_tokens) <= target_tokens:
                trimmed_text.append(line)
                current_tokens += len(line_tokens)
            else:
                # If line exceeds remaining tokens, split by characters
                remaining_tokens = target_tokens - current_tokens
                if remaining_tokens > 0:
                    # Decode back a subset of tokens
                    partial_line = self.encoding.decode(line_tokens[:remaining_tokens])
                    trimmed_text.append(partial_line)
                break

        result = '\n'.join(trimmed_text)
        final_tokens = self.encoding.encode(result)
        if len(final_tokens) > self.max_tokens:
            result = self.encoding.decode(final_tokens[:self.max_tokens])
        return result

    def gather_child_content(self, item):
        """Recursively gather content from child scenes."""
        content = ""
        if item.childCount() == 0:
            data = item.data(0, Qt.UserRole)
            hierarchy = self._get_hierarchy(item)
            if len(hierarchy) < 2: # Only gather content for scenes
                return content
            text = load_latest_autosave(self.project_name, hierarchy) or data.get("content", "")
            content += text + "\n"
        else:
            for i in range(item.childCount()):
                content += self.gather_child_content(item.child(i))
        return content

    def _get_hierarchy(self, item):
        hierarchy = []
        temp = item
        while temp:
            hierarchy.insert(0, temp.text(0).strip())
            temp = temp.parent()
        return hierarchy

    def build_final_prompt(self, prompt, content):
        """Build the final prompt text for preview."""
        return f"### User {prompt.get('text')}\n\nContent:\n{content}"

from settings.autosave_manager import load_latest_autosave
