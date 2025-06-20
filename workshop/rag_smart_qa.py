import os
from typing import List, Dict, Optional
from difflib import SequenceMatcher
import re
import json
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QHBoxLayout, QLineEdit, QPushButton, QTextEdit, 
                             QProgressBar, QFileDialog, QMessageBox, QGridLayout, QComboBox, QDoubleSpinBox, 
                             QPlainTextEdit, QLabel, QSpinBox, QSplitter)
from PyQt5.QtGui import QTextOption

from .rag_utils import TokenCounter, PdfProcessingWorker, LlmClient, SettingsManager, HistoryDialog, AppSettings, PdfProcessor, DocumentProcessorFactory, EpubProcessingWorker, GenericProcessingWorker

class EnhancedPdfProcessor:
    @staticmethod
    def semantic_with_boost(
        full_text: str,
        question: str,
        min_semantic: float = 0.2,
        top_k: int = 5,
        window: int = 1
    ) -> List[Dict]:
        """
        Perform semantic similarity search with keyword-based boost.
        Returns up to top_k paragraphs plus surrounding context.
        """
        query_clean = question.lower().strip()
        words = [w.strip('.,?!') for w in query_clean.split() if w]
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', full_text) if p.strip()]
        results = []

        for idx, para in enumerate(paragraphs):
            para_lower = para.lower()
            sim = SequenceMatcher(None, query_clean, para_lower).ratio()
            kw_hits = sum(bool(re.search(rf'\b{re.escape(w)}\b', para_lower)) for w in words)
            score = 0.7 * sim + 0.3 * (kw_hits / max(1, len(words)))
            if score >= min_semantic:
                results.append({
                    "paragraph_id": idx,
                    "text": para,
                    "match_type": "semantic+boost",
                    "score": round(score, 2),
                    "keyword_hits": kw_hits
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:top_k]

        for hit in results:
            idx = hit["paragraph_id"]
            start = max(0, idx - window)
            end   = min(len(paragraphs) - 1, idx + window)
            hit["context"] = "\n\n".join(paragraphs[start:end+1])

        return results

    @staticmethod
    def semantic_only(
        full_text: str,
        question: str,
        min_similarity: float = 0.2,
        top_k: int = 5,
        window: int = 1
    ) -> List[Dict]:
        """
        Perform pure semantic similarity search.
        Returns up to top_k paragraphs plus surrounding context.
        """
        query_clean = question.lower().strip()
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', full_text) if p.strip()]
        results = []

        for idx, para in enumerate(paragraphs):
            sim = SequenceMatcher(None, query_clean, para.lower()).ratio()
            if sim >= min_similarity:
                results.append({
                    "paragraph_id": idx,
                    "text": para,
                    "match_type": "semantic",
                    "score": round(sim, 2)
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:top_k]

        for hit in results:
            idx = hit["paragraph_id"]
            start = max(0, idx - window)
            end   = min(len(paragraphs) - 1, idx + window)
            hit["context"] = "\n\n".join(paragraphs[start:end+1])

        return results

    @staticmethod
    def keyword_only(
        full_text: str,
        question: str,
        top_k: int = 5,
        window: int = 1
    ) -> List[Dict]:
        """
        Perform exact keyword search. Treats every word in the question as keyword.
        Returns up to top_k paragraphs plus surrounding context.
        """
        query_clean = question.lower().strip()
        words = [w.strip('.,?!') for w in query_clean.split() if w]
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', full_text) if p.strip()]
        results = []

        for idx, para in enumerate(paragraphs):
            para_lower = para.lower()
            kw_hits = sum(1 for w in words if re.search(rf'\b{re.escape(w)}\b', para_lower))
            if kw_hits > 0:
                score = round(kw_hits / len(words), 2)
                results.append({
                    "paragraph_id": idx,
                    "text": para,
                    "match_type": "keyword",
                    "score": score,
                    "keyword_hits": kw_hits
                })

        results.sort(key=lambda x: (x["keyword_hits"], x["score"]), reverse=True)
        results = results[:top_k]

        for hit in results:
            idx = hit["paragraph_id"]
            start = max(0, idx - window)
            end   = min(len(paragraphs) - 1, idx + window)
            hit["context"] = "\n\n".join(paragraphs[start:end+1])

        return results

class SimpleQaSystem:
    @staticmethod
    def generate_answer(
        question: str,
        context: List[Dict],
        extra_instructions: str = ""
    ) -> tuple[str, dict]:
        """
        Always send every entry in context, no token-limit.
        Returns tuple: (answer, token_stats)
        """
        if not context:
            return "No relevant information found in the document.", {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }

        context_str = ""
        for entry in context:
            context_str += f"\n\n[Paragraph {entry['paragraph_id']}] {entry['text']}"

        prompt_parts = [
            f"**Question:**\n{question}",
            f"**Context:**{context_str}"
        ]
        if extra_instructions:
            prompt_parts.append(f"**User Instructions (priority):**\n{extra_instructions}")
        else:
            prompt_parts.append("**Rules:**\n1. Be precise.\n2. If unsure, say \"I don't know.\"\n3. Mention paragraph numbers.")

        prompt = "\n\n".join(prompt_parts)
        
        # Count prompt tokens before sending to LLM
        prompt_tokens = TokenCounter.count_tokens(prompt)
        
        response, _ = LlmClient.send_prompt(prompt)
        
        # Count completion tokens from the actual response
        completion_tokens = TokenCounter.count_tokens(response)
        total_tokens = prompt_tokens + completion_tokens
        
        token_stats = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens
        }
        
        return response, token_stats

class QaWorker(QThread):
    finished = pyqtSignal(str, list)
    error = pyqtSignal(str)

    def __init__(self, markdown_text, question, mode,
                 min_sim, top_k, context_mode,
                 custom_instr, snippet_length):
        super().__init__()
        self.markdown_text   = markdown_text
        self.question        = question
        self.mode            = mode
        self.min_sim         = min_sim
        self.top_k           = top_k
        self.context_mode    = context_mode
        self.custom_instr    = custom_instr
        self.snippet_length  = snippet_length

    def run(self):
        try:
            cm = self.context_mode
            if cm.startswith("Snippet"):
                snippet_mode = True
                window = 0
            elif "Surrounding" in cm:
                snippet_mode = False
                try:
                    window = int(cm.split()[-2])
                except (ValueError, IndexError):
                    window = 1
            elif cm.startswith("Full Paragraph"):
                snippet_mode = False
                window = 0
            else:
                snippet_mode = False
                window = 0

            if "Boost" in self.mode:
                relevant_sections = EnhancedPdfProcessor.semantic_with_boost(
                    full_text=self.markdown_text,
                    question=self.question,
                    min_semantic=self.min_sim,
                    top_k=self.top_k,
                    window=window
                )
            elif "Semantic" in self.mode:
                relevant_sections = EnhancedPdfProcessor.semantic_only(
                    full_text=self.markdown_text,
                    question=self.question,
                    min_similarity=self.min_sim,
                    top_k=self.top_k,
                    window=window
                )
            else:
                relevant_sections = EnhancedPdfProcessor.keyword_only(
                    full_text=self.markdown_text,
                    question=self.question,
                    top_k=self.top_k,
                    window=window
                )

            if snippet_mode:
                llm_context = [
                    {
                        "paragraph_id": sec["paragraph_id"],
                        "text": sec["text"][:self.snippet_length],
                        "score": sec.get("score", 1.0)
                    }
                    for sec in relevant_sections
                ]
            else:
                llm_context = []
                for sec in relevant_sections:
                    block = sec.get("context", sec["text"])
                    llm_context.append({
                        "paragraph_id": sec["paragraph_id"],
                        "text": block,
                        "score": sec.get("score", 1.0)
                    })

            # Get answer and token statistics
            answer, token_stats = SimpleQaSystem.generate_answer(
                question=self.question,
                context=llm_context,
                extra_instructions=self.custom_instr
            )

            result_text  = f"Question: {self.question}\n\n"
            result_text += f"Answer:\n{answer}\n\n"
            result_text += "Relevant paragraphs:\n"
            for sec in relevant_sections:
                result_text += (
                    f"\nParagraph {sec['paragraph_id']} "
                    f"(score: {sec.get('score', 1.0):.2f}):\n"
                    f"{sec['text']}\n"
                )
            
            # Add token information
            result_text += f"\n\n--- Token Usage ---\n"
            result_text += f"Prompt tokens: {token_stats['prompt_tokens']:,}\n"
            result_text += f"Completion tokens: {token_stats['completion_tokens']:,}\n"
            result_text += f"Total tokens: {token_stats['total_tokens']:,}\n"
            result_text += "~ Note: Token counts are approximate and may vary across models, due to different tokenization methods."

            self.finished.emit(result_text, relevant_sections)

        except Exception as e:
            self.error.emit(f"Error: {str(e)}")

class SmartQAWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.MIN_SIMILARITY_DEFAULT = 0.3
        self.TOP_K_DEFAULT = 50
        self.SNIPPET_LENGTH = 500
        self.parent_app = parent
        self.init_qa_tab()

    def init_qa_tab(self):
        # Create a vertical layout for the entire tab
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Create a vertical splitter so the user can resize/hide the top or bottom pane
        splitter = QSplitter(Qt.Vertical, self)

        # -----------------------------------------
        # Upper Pane Container (all controls/input)
        # -----------------------------------------
        upper_container = QWidget()
        upper_layout = QVBoxLayout(upper_container)
        upper_layout.setSpacing(10)
        upper_layout.setContentsMargins(0, 0, 0, 0)

        # --- PDF Selection Group ---
        pdf_group = QGroupBox("Document Selection", upper_container)
        pdf_layout = QHBoxLayout()
        pdf_layout.setSpacing(8)

        self.qa_pdf_path_edit = QLineEdit()
        self.qa_pdf_path_edit.setPlaceholderText("Select document file...")
        self.qa_pdf_path_edit.textChanged.connect(self.on_qa_pdf_path_changed)
        self.qa_pdf_path_edit.returnPressed.connect(
            lambda: self.process_qa_pdf() if self.qa_process_btn.isEnabled() else None
        )
        pdf_layout.addWidget(self.qa_pdf_path_edit, 1)

        clear_path_btn = QPushButton("×")
        clear_path_btn.setFixedWidth(24)
        clear_path_btn.setToolTip("Clear path")
        clear_path_btn.clicked.connect(lambda: self.qa_pdf_path_edit.clear())
        pdf_layout.addWidget(clear_path_btn)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_qa_pdf)
        pdf_layout.addWidget(browse_btn)

        pdf_group.setLayout(pdf_layout)
        upper_layout.addWidget(pdf_group)

        # --- Process Button and Status ---
        process_layout = QHBoxLayout()
        process_layout.setSpacing(8)

        self.qa_process_btn = QPushButton("Process Document")
        self.qa_process_btn.clicked.connect(self.process_qa_pdf)
        self.qa_process_btn.setEnabled(False)
        process_layout.addWidget(self.qa_process_btn)

        self.qa_status_label = QLabel("No document loaded")
        self.qa_status_label.setStyleSheet("color: #888888; font-style: italic;")
        process_layout.addWidget(self.qa_status_label, 1)

        upper_layout.addLayout(process_layout)

        self.qa_progress_bar = QProgressBar()
        self.qa_progress_bar.setVisible(False)
        self.qa_progress_bar.setFormat("%p% - %v/%m pages processed")
        upper_layout.addWidget(self.qa_progress_bar)

        # --- Settings Group ---
        settings_group = QGroupBox("Search Mode & Settings", upper_container)
        settings_layout = QGridLayout()
        settings_layout.setSpacing(8)
        settings_layout.setColumnStretch(1, 1)

        # Search Mode Combo
        settings_layout.addWidget(QLabel("Search Mode:"), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Semantic + Keyword Boost",
            "Semantic Search Only",
            "Exact Keyword Matching"
        ])
        self.mode_combo.setToolTip(
            "Select search mode:\n"
            "- Semantic + Keyword Boost: combine semantic similarity with keyword hits\n"
            "- Semantic Search Only: use only semantic similarity\n"
            "- Exact Keyword Matching: match exact keywords only"
        )
        self.mode_combo.currentIndexChanged.connect(self.update_search_ui_state)
        settings_layout.addWidget(self.mode_combo, 0, 1)

        # Min Similarity SpinBox
        settings_layout.addWidget(QLabel("Min Similarity:"), 1, 0)
        self.min_similarity_spin = QDoubleSpinBox()
        self.min_similarity_spin.setRange(0.0, 1.0)
        self.min_similarity_spin.setSingleStep(0.05)
        self.min_similarity_spin.setValue(self.MIN_SIMILARITY_DEFAULT)
        self.min_similarity_spin.setDecimals(2)
        self.min_similarity_spin.setSuffix("%")
        self.min_similarity_spin.setSpecialValueText("0% (Include All)")
        self.min_similarity_spin.setToolTip(
            "Minimum semantic similarity threshold (0.0–1.0). Higher → stricter matching."
        )
        settings_layout.addWidget(self.min_similarity_spin, 1, 1)

        # Top K Results SpinBox
        settings_layout.addWidget(QLabel("Top K Results:"), 2, 0)
        self.top_k_spin = QSpinBox()
        self.top_k_spin.setRange(1, 999)
        self.top_k_spin.setValue(self.TOP_K_DEFAULT)
        self.top_k_spin.setSuffix(" paragraphs")
        self.top_k_spin.setToolTip("Maximum number of paragraphs to retrieve.")
        settings_layout.addWidget(self.top_k_spin, 2, 1)

        # Snippet Length SpinBox
        settings_layout.addWidget(QLabel("Snippet Length:"), 3, 0)
        self.snippet_length_spin = QSpinBox()
        self.snippet_length_spin.setRange(50, 5000)
        self.snippet_length_spin.setValue(500)  # default 500 chars
        self.snippet_length_spin.setSuffix(" chars")
        self.snippet_length_spin.setToolTip("Number of characters to include for snippet mode.")
        self.snippet_length_spin.valueChanged.connect(self.update_context_mode_items)
        settings_layout.addWidget(self.snippet_length_spin, 3, 1)

        # Context Mode Combo
        settings_layout.addWidget(QLabel("Context Mode:"), 4, 0)
        self.context_mode_combo = QComboBox()
        self.context_mode_combo.setToolTip(
            "Snippet: send first N chars of each paragraph only.\n"
            "Full Paragraph: send entire paragraph.\n"
            "Full Paragraph + Surrounding X: send paragraph plus X paragraphs before/after."
        )
        settings_layout.addWidget(self.context_mode_combo, 4, 1)

        # Extra Instructions TextEdit
        settings_layout.addWidget(QLabel("Extra Instructions:"), 5, 0, Qt.AlignTop)
        self.custom_prompt_edit = QPlainTextEdit()
        self.custom_prompt_edit.setPlaceholderText(
            "Enter additional instructions for the LLM prompt...\n"
            "Example: 'Focus on technical details' or 'Explain in simple terms'"
        )
        self.custom_prompt_edit.setToolTip(
            "These lines will be appended to the built prompt as custom instructions."
        )
        self.custom_prompt_edit.setMaximumHeight(60)
        settings_layout.addWidget(self.custom_prompt_edit, 5, 1)

        settings_group.setLayout(settings_layout)
        upper_layout.addWidget(settings_group)

        # Initialize the items in context_mode_combo using the current snippet length
        self.update_context_mode_items()

        # --- QA Input Group ---
        qa_input_group = QGroupBox("Ask Document", upper_container)
        input_layout = QVBoxLayout()
        input_layout.setSpacing(8)

        self.qa_question = QLineEdit()
        self.qa_question.setPlaceholderText("Type your question about the document...")
        self.qa_question.returnPressed.connect(
            lambda: self.handle_qa_search() if self.qa_search_btn.isEnabled() else None
        )
        input_layout.addWidget(self.qa_question)

        self.qa_search_btn = QPushButton("Find Answers")
        self.qa_search_btn.clicked.connect(self.handle_qa_search)
        self.qa_search_btn.setEnabled(False)
        input_layout.addWidget(self.qa_search_btn)

        qa_input_group.setLayout(input_layout)
        upper_layout.addWidget(qa_input_group)

        # --- Export Button ---
        self.qa_export_btn = QPushButton("Save QA Results")
        self.qa_export_btn.setVisible(False)
        self.qa_export_btn.clicked.connect(self.export_qa_results)
        upper_layout.addWidget(self.qa_export_btn)

        # Add the upper container to the splitter
        splitter.addWidget(upper_container)

        # -----------------------------------------
        # Lower Pane: Results Group
        # -----------------------------------------
        results_group = QGroupBox("Results", self)
        results_layout = QVBoxLayout()
        results_layout.setSpacing(8)

        self.qa_results = QTextEdit()
        self.qa_results.setReadOnly(True)
        self.qa_results.setPlaceholderText("Results will appear here after processing your question...")
        self.qa_results.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.qa_results.setAcceptRichText(True)
        results_layout.addWidget(self.qa_results)

        results_group.setLayout(results_layout)
        splitter.addWidget(results_group)

        # Make sure the splitter is added to the main layout
        main_layout.addWidget(splitter)

        # Optionally set initial splitter sizes (e.g., 1:3 ratio)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        # Initialize internal state
        self.qa_markdown_text = ''
        self.qa_document_processed = False
        self.qa_document_path = ''

        self.update_search_ui_state()

        # If there was a last-used PDF, load it
        if self.parent_app.settings.last_pdf_path_qa and os.path.exists(self.parent_app.settings.last_pdf_path_qa):
            self.qa_pdf_path_edit.setText(self.parent_app.settings.last_pdf_path_qa)
            self.load_qa_pdf_info()
            
    def update_context_mode_items(self):
        """
        Reads the current snippet_length_spin value and updates the items in context_mode_combo.
        """
        # Retrieve the current length of the fragment from the spin box
        n_chars = self.snippet_length_spin.value()

        # Prepare a list of option labels
        items = [
            f"Snippet (first {n_chars} chars)",
            "Full Paragraph",
            "Full Paragraph + Surrounding 1 paragraph",
            "Full Paragraph + Surrounding 2 paragraphs",
            "Full Paragraph + Surrounding 5 paragraphs",
            "Full Paragraph + Surrounding 10 paragraphs"
        ]

        # Clear existing items and add new ones
        self.context_mode_combo.clear()
        self.context_mode_combo.addItems(items)

    def update_search_ui_state(self):
        mode_index = self.mode_combo.currentIndex()
        semantic_mode = mode_index in [0, 1]
        self.min_similarity_spin.setEnabled(semantic_mode)
        self.min_similarity_spin.setPrefix('')
        self.min_similarity_spin.setSuffix('%')
        current_value = self.min_similarity_spin.value()
        self.min_similarity_spin.setValue(current_value)
        self.min_similarity_spin.setSpecialValueText("0% (Include All)")

    def browse_qa_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Document",
            "",
            "Supported files (*.pdf *.epub *.docx *.txt *.md *.html);;"
            "PDF Files (*.pdf);;"
            "EPUB Files (*.epub);;"
            "Word Documents (*.docx);;"
            "Text Files (*.txt *.md);;"
            "HTML Files (*.html);;"
            "All Files (*)"
        )
        if path:
            self.qa_pdf_path_edit.setText(path)
            self.on_qa_pdf_path_changed()

    def on_qa_pdf_path_changed(self):
        path = self.qa_pdf_path_edit.text().strip()
        supported_extensions = ['.pdf', '.epub', '.docx', '.txt', '.md', '.html']
        is_valid_file = any(path.lower().endswith(ext) for ext in supported_extensions) and os.path.isfile(path)
        self.qa_process_btn.setEnabled(is_valid_file)
        self.qa_search_btn.setEnabled(False)

        if not path:
            self.qa_status_label.setText("No document loaded")
            self.qa_status_label.setStyleSheet("color: #888888; font-style: italic;")
        elif is_valid_file:
            self.qa_status_label.setText(f"Ready to process: {os.path.basename(path)}")
            self.qa_status_label.setStyleSheet("color: #006400; font-style: normal;")
            self.load_qa_pdf_info()
        else:
            self.qa_status_label.setText("Invalid file selected")
            self.qa_status_label.setStyleSheet("color: #8B0000; font-style: italic;")

    def load_qa_pdf_info(self):
        # Load document info for any supported file type
        path = self.qa_pdf_path_edit.text().strip()
        try:
            processor = DocumentProcessorFactory.get_processor(path)
            section_count, error = processor.load_document(path)
            if error:
                QMessageBox.warning(self, "Document Error", error)
                return
            self.parent_app.settings.last_pdf_path_qa = path  # Keeping name for compatibility
            SettingsManager.save_settings(self.parent_app.settings)
            self.qa_document_path = path
        except ValueError as e:
            QMessageBox.warning(self, "Unsupported Format", str(e))

    def process_qa_pdf(self):
        """
        Called when user clicks “Process”. Chooses the correct worker
        (PDF vs EPUB vs others) based on file extension.
        """
        file_path = self.qa_pdf_path_edit.text().strip()
        if not file_path or not os.path.isfile(file_path):
            QMessageBox.warning(self, "Error", "Invalid file selected.")
            return

        try:
            ext = os.path.splitext(file_path)[1].lower()
            processor = DocumentProcessorFactory.get_processor(file_path)
            section_count, error = processor.load_document(file_path)
            if error:
                QMessageBox.warning(self, "Document Error", error)
                return

            # build list of all sections (chapters/pages/etc.)
            sections = list(range(0, section_count))

            # show progress
            self.qa_progress_bar.setVisible(True)
            self.qa_progress_bar.setRange(0, 0)
            self.qa_process_btn.setEnabled(False)
            self.qa_search_btn.setEnabled(False)

            # choose worker
            if ext == '.epub':
                from .rag_utils import EpubProcessingWorker
                self.qa_worker = EpubProcessingWorker(file_path, sections)

            elif ext == '.pdf':
                from .rag_utils import PdfProcessingWorker
                self.qa_worker = PdfProcessingWorker(file_path, sections)

            else:
                from .rag_utils import GenericProcessingWorker
                self.qa_worker = GenericProcessingWorker(file_path, sections)

            # connect and start
            self.qa_worker.finished.connect(self.on_qa_pdf_processing_finished)
            self.qa_worker.start()

        except ValueError as e:
            QMessageBox.warning(self, "Unsupported Format", str(e))

    def on_qa_pdf_processing_finished(self, markdown: str, chunks: List[str], error: str):
        # Handle processing completion for any document type
        self.qa_progress_bar.setVisible(False)
        self.qa_process_btn.setEnabled(True)
        
        if error:
            QMessageBox.critical(self, "Processing Error", error)
            self.qa_status_label.setText("Document processing failed")
            self.qa_status_label.setStyleSheet("color: #8B0000; font-style: italic;")
            self.qa_search_btn.setEnabled(False)
            return
        
        self.qa_markdown_text = markdown
        self.parent_app.status_bar.showMessage("Document processed for Smart QA", 5000)
        self.qa_search_btn.setEnabled(True)
        self.qa_status_label.setText(f"Document ready: {os.path.basename(self.qa_document_path)}")
        self.qa_status_label.setStyleSheet("color: #006400; font-style: normal;")

    def export_qa_results(self):
        if not self.qa_markdown_text:
            QMessageBox.warning(self, "Error", "No QA results to save.")
            return

        data = {
            "pdf_path": self.qa_document_path,
            "question": self.qa_question.text().strip(),
            "answer": self.qa_markdown_text
        }

        pdf_base = os.path.splitext(os.path.basename(self.qa_pdf_path_edit.text().strip()))[0]
        default_name = f"{pdf_base}_qa_results"
        suggested_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Save QA Results",
            "Enter filename (no extension):",
            text=default_name
        )
        if not ok or not suggested_name.strip():
            return
        filename = suggested_name.strip() + ".json"
        save_path = os.path.join(self.parent_app.history_dir, filename)

        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.parent_app.status_bar.showMessage(f"Saved QA JSON to {save_path}", 5000)
            self.parent_app.search_history.append((filename, self.qa_markdown_text))
            self.parent_app.save_history()
            self.parent_app.status_bar.showMessage(f"History updated with {filename}", 5000)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save QA results: {e}")

    def handle_qa_search(self):
        question = self.qa_question.text().strip()
        if not question:
            QMessageBox.warning(self, "Error", "Please enter a question first.")
            return

        self.parent_app.set_busy_cursor()
        self.qa_search_btn.setEnabled(False)
        self.qa_status_label.setText("Processing...")
        QtWidgets.QApplication.processEvents()

        mode = self.mode_combo.currentText()
        min_sim = self.min_similarity_spin.value()
        top_k = self.top_k_spin.value()
        context_mode = self.context_mode_combo.currentText()
        custom_instr = self.custom_prompt_edit.toPlainText()

        self.qa_worker = QaWorker(
            self.qa_markdown_text,
            question,
            mode,
            min_sim,
            top_k,
            context_mode,
            custom_instr,
            self.SNIPPET_LENGTH
        )
        self.qa_worker.finished.connect(self.on_qa_success)
        self.qa_worker.error.connect(self.on_qa_error)
        self.qa_worker.start()

    def on_qa_success(self, result_text, relevant_sections):
        self.parent_app.restore_cursor()
        self.qa_results.setPlainText(result_text)
        self.qa_status_label.setText("Ready")
        self.qa_export_btn.setVisible(True)
        self.qa_export_btn.setEnabled(True)
        self.qa_search_btn.setEnabled(True)

    def on_qa_error(self, error_msg):
        self.parent_app.restore_cursor()
        self.qa_status_label.setText("Error")
        self.qa_search_btn.setEnabled(True)
        QMessageBox.critical(self, "Processing Error", error_msg)