import sys
import platform
import math
import tiktoken
import os
import json
import datetime
import logging
logging.getLogger("boilerpy3").setLevel(logging.ERROR)
logging.getLogger("qt.fonts").setLevel(logging.ERROR)
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import QUrl, Qt, QThread, pyqtSignal, QDir
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QFileDialog, QMessageBox,
    QGroupBox, QPlainTextEdit, QSplitter, QLabel,
    QCheckBox, QListWidget, QDialog, QDialogButtonBox,
    QSpinBox, QMenu, QAction, QToolButton, QComboBox,
    QMenuBar, QShortcut, QInputDialog
)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile, QWebEngineContextMenuData, QWebEngineSettings
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
from boilerpy3 import extractors
from bs4 import BeautifulSoup, NavigableString
import re
from settings.llm_api_aggregator import WWApiAggregator
from settings.theme_manager import ThemeManager

class SilentPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        pass

class CustomWebView(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.network_manager = QNetworkAccessManager(self)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        hit_result = self.page().contextMenuData()

        if hit_result.mediaType() == QWebEngineContextMenuData.MediaTypeImage:
            save_image_action = QAction("Save image as...", self)
            save_image_action.triggered.connect(lambda: self.save_image(hit_result.mediaUrl()))
            menu.addAction(save_image_action)

        menu.exec_(event.globalPos())

    def save_image(self, image_url):
        if not image_url.isValid():
            QMessageBox.warning(self, "Error", "Invalid image URL.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if not file_path:
            return

        request = QNetworkRequest(image_url)
        reply = self.network_manager.get(request)
        reply.finished.connect(lambda: self.write_image_to_file(reply, file_path))

    def write_image_to_file(self, reply, file_path):
        if reply.error() == 0:
            image_data = reply.readAll()
            with open(file_path, 'wb') as f:
                f.write(image_data)
            QMessageBox.information(self, "Success", f"Image saved to:\n{file_path}")
        else:
            QMessageBox.critical(self, "Error", f"Failed to download image: {reply.errorString()}")

class LLMWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, prompt, content, conversation_history=None):
        super().__init__()
        self.prompt = prompt
        self.content = content
        self.conversation_history = conversation_history or []

    def run(self):
        try:
            history_text = ""
            if self.conversation_history:
                history_text = "Previous conversation:\n" + "\n".join([
                    f"User: {item['prompt']}\nAssistant: {item['response']}"
                    for item in self.conversation_history
                ]) + "\n\n"
            
            full_prompt = f"{history_text}User: {self.prompt}\n\nWeb Content:\n{self.content}"
            response = WWApiAggregator.send_prompt_to_llm(full_prompt)
            self.finished.emit(response)
        except Exception as e:
            self.error.emit(str(e))

class ConversationHistoryDialog(QDialog):
    def __init__(self, history, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conversation History")
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.textChanged.connect(self.filter_history)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        self.history_list = QListWidget()
        self.full_history = history
        self.update_history_list(history)
        
        layout.addWidget(self.history_list)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def update_history_list(self, history):
        self.history_list.clear()
        for i, item in enumerate(history):
            self.history_list.addItem(f"Q{i+1}: {item['prompt'][:50]}...")
    
    def filter_history(self, text):
        filtered = [item for item in self.full_history if text.lower() in item['prompt'].lower()]
        self.update_history_list(filtered)

class MainWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Web Text Extractor with LLM")
        self.resize(1100, 800)
        
        # Add the use_history flag to track whether to include conversation history
        self.use_history = False
        
        if platform.system() == 'Linux':
            self.check_dependencies()
            
        self.web_history_dir = os.path.join(QDir.currentPath(), "web_history")
        if not os.path.exists(self.web_history_dir):
            os.makedirs(self.web_history_dir)
            
        self.conversation_history = []
        history_file = os.path.join(self.web_history_dir, "history.json")
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                self.conversation_history = json.load(f)
        
        self.init_ui()
        self.extractor = extractors.ArticleExtractor()
        
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            print(f"Failed to initialize tokenizer: {e}")
            self.encoding = None
            
        self.current_content = ""
        self.original_content = ""
        self.current_url = ""
        self.load_home()

        self.web_view.loadStarted.connect(self._clear_find_highlight)

        self.shortcut_find = QShortcut(QKeySequence("Ctrl+F"), self)
        self.shortcut_find.setContext(Qt.ApplicationShortcut)
        self.shortcut_find.activated.connect(self.open_find_dialog)

    def check_dependencies(self):
        try:
            _ = QWebEngineView()
        except Exception:
            QMessageBox.critical(
                None, "Missing Dependencies",
                "Qt WebEngine dependencies not found.\n"
                "Please install: sudo apt-get install libqt5webengine5 qt5-webengine-dev"
            )
            sys.exit(1)

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.create_menu_bar()
        toolbar = QHBoxLayout()
        
        back_btn = QToolButton()
        back_btn.setIcon(ThemeManager.get_tinted_icon("assets/icons/arrow-left.svg"))
        back_btn.clicked.connect(lambda: self.web_view.back())
        toolbar.addWidget(back_btn)

        forward_btn = QToolButton()
        forward_btn.setIcon(ThemeManager.get_tinted_icon("assets/icons/arrow-right.svg"))
        forward_btn.clicked.connect(lambda: self.web_view.forward())
        toolbar.addWidget(forward_btn)

        reload_btn = QToolButton()
        reload_btn.setIcon(ThemeManager.get_tinted_icon("assets/icons/refresh-cw.svg"))
        reload_btn.clicked.connect(lambda: self.web_view.reload())
        toolbar.addWidget(reload_btn)

        home_btn = QToolButton()
        home_btn.setIcon(ThemeManager.get_tinted_icon("assets/icons/home.svg"))
        home_btn.clicked.connect(self.load_home)
        toolbar.addWidget(home_btn)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter URL...")
        self.url_input.setText("https://www.wikipedia.org/")
        toolbar.addWidget(self.url_input)

        load_btn = QToolButton()
        load_btn.setIcon(ThemeManager.get_tinted_icon("assets/icons/search.svg"))
        load_btn.clicked.connect(self.load_url)
        toolbar.addWidget(load_btn)
        
        self.offline_checkbox = QCheckBox("Save for Offline")
        self.offline_checkbox.stateChanged.connect(self.toggle_offline_mode)
        self.offline_checkbox.setToolTip("Automatically save copies of all visited pages.")
        toolbar.addWidget(self.offline_checkbox)
        
        load_cache_btn = QPushButton("Browse Offline Library")
        load_cache_btn.clicked.connect(self.show_cache_dialog)
        toolbar.addWidget(load_cache_btn)

        layout.addLayout(toolbar)

        token_bar = QHBoxLayout()
        
        token_info = QVBoxLayout()
        
        token_row1 = QHBoxLayout()
        self.token_label = QLabel("Original Tokens: 0")
        self.token_label.setStyleSheet("font-weight: bold;")
        token_row1.addWidget(self.token_label)
        
        self.processed_token_label = QLabel("Processed Tokens: 0")
        self.processed_token_label.setStyleSheet("font-weight: bold;")
        token_row1.addWidget(self.processed_token_label)
        token_info.addLayout(token_row1)
        
        token_row2 = QHBoxLayout()
        self.content_size_label = QLabel("Original Content: 0 chars")
        token_row2.addWidget(self.content_size_label)
        
        self.processed_size_label = QLabel("Processed Content: 0 chars")
        token_row2.addWidget(self.processed_size_label)
        token_info.addLayout(token_row2)
        
        token_bar.addLayout(token_info)
        
        token_settings = QHBoxLayout()
        token_settings.addWidget(QLabel("Max Tokens:"))
        
        self.max_tokens_input = QSpinBox()
        self.max_tokens_input.setRange(100, 1000000)
        self.max_tokens_input.setValue(32000)
        self.max_tokens_input.setSingleStep(500)
        self.max_tokens_input.valueChanged.connect(self.update_token_calculations)
        token_settings.addWidget(self.max_tokens_input)
        
        token_bar.addLayout(token_settings)
        
        layout.addLayout(token_bar)

        self.web_view = CustomWebView()
        
        self.web_profile = QWebEngineProfile("storage", self.web_view)
        self.web_profile.setCachePath(os.path.join(self.web_history_dir, "cache"))
        self.web_profile.setPersistentStoragePath(os.path.join(self.web_history_dir, "storage"))
        self.web_profile.setHttpUserAgent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        
        silent_page = SilentPage(self.web_profile, self.web_view)
        self.web_view.setPage(silent_page)

        llm_group = QGroupBox("LLM Interaction")
        llm_layout = QVBoxLayout()
        
        history_layout = QHBoxLayout()
        history_layout.addWidget(QLabel("Conversation:"))
        
        view_history_btn = QPushButton("View History")
        view_history_btn.clicked.connect(self.view_conversation_history)
        history_layout.addWidget(view_history_btn)
        
        clear_history_btn = QPushButton("Clear History")
        clear_history_btn.clicked.connect(self.clear_conversation_history)
        history_layout.addWidget(clear_history_btn)
        
        # Extractor ComboBox moved from toolbar to here (between Clear History and Use Original Content)
        self.extractor_combo = QComboBox()
        self.extractor_combo.addItems([
            "DefaultExtractor",
            "ArticleExtractor",
            "ArticleSentencesExtractor",
            "LargestContentExtractor",
            "CanolaExtractor",
            "KeepEverythingExtractor",
            "NumWordsRulesExtractor"
        ])
        self.extractor_combo.setToolTip("Select text extraction method")
        self.extractor_combo.setCurrentText("ArticleExtractor")  # default
        self.extractor_combo.currentTextChanged.connect(self.on_extractor_changed)
        history_layout.addWidget(self.extractor_combo)
        
        self.use_original_checkbox = QCheckBox("Use Original Content")
        self.use_original_checkbox.setToolTip(
            "Send original page text instead of processed version to LLM."
        )
        self.use_original_checkbox.stateChanged.connect(self.update_total_tokens)
        history_layout.addWidget(self.use_original_checkbox)
        
        history_layout.addStretch()
        llm_layout.addLayout(history_layout)
        
        prompt_header = QHBoxLayout()
        prompt_header.addWidget(QLabel("Enter your question or instruction:"))
        self.prompt_token_label = QLabel("Prompt tokens: 0")
        prompt_header.addWidget(self.prompt_token_label)
        llm_layout.addLayout(prompt_header)
        
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Enter your question or instruction...")
        self.prompt_input.textChanged.connect(self.update_prompt_tokens)
        llm_layout.addWidget(self.prompt_input)

        total_token_layout = QHBoxLayout()
        self.total_token_label = QLabel("Total tokens: 0")
        self.total_token_label.setStyleSheet("font-weight: bold;")
        total_token_layout.addWidget(self.total_token_label)
        
        self.send_btn = QPushButton("Ask LLM")
        self.send_btn.clicked.connect(self.start_llm_query)
        total_token_layout.addWidget(self.send_btn)
        
        edit_content_btn = QPushButton("Edit Content")
        edit_content_btn.clicked.connect(self.edit_content)
        edit_content_btn.setToolTip("Edit processed content of the web page before sending to LLM.")
        total_token_layout.addWidget(edit_content_btn)
        
        preview_btn = QPushButton("Preview Prompt")
        preview_btn.clicked.connect(self.preview_prompt)
        total_token_layout.addWidget(preview_btn)
        
        llm_layout.addLayout(total_token_layout)

        self.response_area = QPlainTextEdit()
        self.response_area.setReadOnly(True)
        self.response_area.setPlaceholderText("LLM response will appear here...")
        llm_layout.addWidget(self.response_area)

        llm_group.setLayout(llm_layout)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.web_view)
        splitter.addWidget(llm_group)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setHandleWidth(8)
        splitter.setStyleSheet("QSplitter::handle { background-color: #ccc }")

        layout.addWidget(splitter)

        bottom_bar = QHBoxLayout()
        
        self.save_text_btn = QPushButton("Save Text")
        self.save_text_btn.setEnabled(False)
        self.save_text_btn.clicked.connect(self.on_save)
        bottom_bar.addWidget(self.save_text_btn)

        self.save_pdf_btn = QPushButton("Save as PDF")
        self.save_pdf_btn.setEnabled(False)
        self.save_pdf_btn.clicked.connect(self.save_as_pdf)
        bottom_bar.addWidget(self.save_pdf_btn)

        layout.addLayout(bottom_bar)

        self.web_view.loadStarted.connect(self.on_load_started)
        self.web_view.loadFinished.connect(self.on_load_finished)
        
    def create_menu_bar(self):
        menu_bar = QMenuBar(self)
               
        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_app_info)
        help_menu.addAction(about_action)
        
        self.layout().setMenuBar(menu_bar)

    def show_app_info(self):
        about_text = """
        <h2>Web Browser-Editor with LLM Integration</h2>
        <p>This advanced browser-editor window integrates with Language Models for content processing and analysis.</p>
        <h3>Features:</h3>
        <ul>
            <li>Web browsing with page saving for offline mode</li>
            <li>Content extraction to remove template elements (ads, menus)</li>
            <li>AI integration - send processed content to language models</li>
            <li>Text analysis - token statistics, content trimming, prompt previews</li>
            <li>Resource management - page caching, offline library, PDF/TXT export</li>
        </ul>
        <h3>Extractor Types:</h3>
        <ul>
            <li><b>DefaultExtractor</b> - Generic full-text extractor, simpler but typically less effective than ArticleExtractor</li>
            <li><b>ArticleExtractor</b> - Tuned for news articles, high accuracy for article-like HTML</li>
            <li><b>ArticleSentencesExtractor</b> - Specialized for extracting sentences from news articles</li>
            <li><b>LargestContentExtractor</b> - Extracts the largest text component of a page</li>
            <li><b>CanolaExtractor</b> - Full-text extractor trained on krdwrd Canola</li>
            <li><b>KeepEverythingExtractor</b> - Returns the entire input text without filtering</li>
            <li><b>NumWordsRulesExtractor</b> - Generic extractor based on word count per block</li>
        </ul>
        <h3>Usage:</h3>
        <ul>
            <li>Browse websites and manage history/bookmarks</li>
            <li>Select extraction method for content processing</li>
            <li>Manage conversation history and tokens with LLM integration</li>
            <li>Analyze text statistics and preview prompts before sending to AI</li>
            <li>Save content offline or export to PDF/TXT formats</li>
        </ul>
        """
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("About")
        msg_box.setText(about_text)
        msg_box.setTextFormat(Qt.RichText)
        msg_box.exec_()

    def toggle_offline_mode(self, state):
        """
        Disable JavaScript and switch to disk cache when offline checkbox is checked;
        otherwise re-enable JavaScript and use in-memory cache.
        """
        settings = self.web_view.page().settings()
        if state == Qt.Checked:
            # Disable JS and persist cache to disk
            settings.setAttribute(QWebEngineSettings.JavascriptEnabled, False)
            self.web_profile.setHttpCacheType(QWebEngineProfile.DiskHttpCache)
        else:
            # Re-enable JS and use in-memory cache
            settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            self.web_profile.setHttpCacheType(QWebEngineProfile.MemoryHttpCache)

    def show_cache_dialog(self):
        """
        Show cached pages with filter and allow deletion of individual entries.
        """
        # 1) Load metadata
        cache_files = []
        for fn in os.listdir(self.web_history_dir):
            if fn.endswith('.json') and fn != 'history.json':
                path = os.path.join(self.web_history_dir, fn)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        d = json.load(f)
                        cache_files.append({
                            'title':    d.get('title', 'Unknown'),
                            'url':      d.get('url', 'Unknown'),
                            'date':     d.get('date', 'Unknown'),
                            'filepath': path
                        })
                except Exception as e:
                    print(f"Error reading cache file {fn}: {e}")

        if not cache_files:
            QMessageBox.information(self, "Cache", "No cached content found.")
            return

        # 2) Build dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Cached Page")
        dialog.resize(500, 350)
        layout = QVBoxLayout(dialog)

        # 3) Filter input
        filter_edit = QLineEdit(dialog)
        filter_edit.setPlaceholderText("Filter by title, URL, or date…")
        layout.addWidget(filter_edit)

        # 4) List widget
        list_widget = QListWidget(dialog)
        layout.addWidget(list_widget)

        # 5) Maintain and refresh filtered list
        filtered = []
        def update_list():
            txt = filter_edit.text().lower()
            filtered.clear()
            list_widget.clear()
            for item in cache_files:
                if txt in f"{item['title']} {item['url']} {item['date']}".lower():
                    filtered.append(item)
                    list_widget.addItem(f"{item['title']} - {item['url']} ({item['date']})")

        filter_edit.textChanged.connect(update_list)
        update_list()

        # 6) Delete button
        delete_btn = QPushButton("Delete Selected", dialog)
        def delete_selected():
            row = list_widget.currentRow()
            if row < 0:
                return
            to_delete = filtered[row]
            try:
                os.remove(to_delete['filepath'])
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Cannot delete file: {e}")
                return
            # remove from master and filtered, then refresh
            cache_files.remove(to_delete)
            update_list()
        delete_btn.clicked.connect(delete_selected)
        layout.addWidget(delete_btn)

        # 7) OK / Cancel
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        # 8) Execute and load or delete
        if dialog.exec_() == QDialog.Accepted and list_widget.currentRow() >= 0:
            sel = filtered[list_widget.currentRow()]
            self.load_from_cache(sel['filepath'])

    def load_from_cache(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                self.url_input.setText(data.get('url', ''))
                self.current_url = data.get('url', '')
                
                self.original_content = data.get('original_content', '')
                self.current_content = data.get('processed_content', '')
                
                # When loading from cache, we should reset use_history flag 
                # as we're starting a new browsing session
                self.use_history = False
                
                if self.original_content:
                    orig_token_count = self.count_tokens(self.original_content)
                    self.token_label.setText(f"Original Tokens: {orig_token_count:,}")
                    self.content_size_label.setText(f"Original Content: {len(self.original_content):,} chars")
                
                if self.current_content:
                    processed_token_count = self.count_tokens(self.current_content)
                    self.processed_token_label.setText(f"Processed Tokens: {processed_token_count:,}")
                    self.processed_size_label.setText(f"Processed Content: {len(self.current_content):,} chars")
                    
                    self.save_text_btn.setEnabled(True)
                    self.update_total_tokens()
                    
                if data.get('html'):
                    self.web_view.setHtml(data.get('html'), QUrl(data.get('url', '')))
                else:
                    self.web_view.setHtml(f"<html><body><h1>{data.get('title', 'Cached Content')}</h1><p>Content loaded from cache</p></body></html>")
                
                QMessageBox.information(self, "Cache", "Content loaded from cache successfully.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load cached content: {str(e)}")

    def save_to_cache(self, html, url, title, original_content, processed_content):
        """
        Save page to JSON cache unless the same URL is already cached.
        """
        # 0) Normalize the URL key
        normalized_url = url.rstrip('/')
        # 1) Check for existing cache of same URL
        for fn in os.listdir(self.web_history_dir):
            if fn.endswith('.json') and fn != 'history.json':
                path = os.path.join(self.web_history_dir, fn)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                        if existing.get('url', '').rstrip('/') == normalized_url:
                            # already cached → skip
                            return False
                except Exception:
                    continue

        # 2) Build new cache filename
        safe_filename = re.sub(r'[^a-zA-Z0-9]', '_', url)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_filename}_{timestamp}.json"
        filepath = os.path.join(self.web_history_dir, filename)

        # 3) Prepare data
        data = {
            'url':               url,
            'title':             title,
            'date':              datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'html':              html,
            'original_content':  original_content,
            'processed_content': processed_content
        }

        # 4) Write to disk
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving to cache: {e}")
            return False

    def count_tokens(self, text):
        if not text or not self.encoding:
            return 0
        try:
            tokens = self.encoding.encode(text)
            return len(tokens)
        except Exception as e:
            print(f"Error counting tokens: {e}")
            return 0

    def load_home(self):
        home_url = "https://www.wikipedia.org/"
        self.url_input.setText(home_url)
        self.web_view.load(QUrl(home_url))
        self.current_url = home_url

    def load_url(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Warning", "Please enter a valid URL.")
            return
        if not url.lower().startswith(('http://', 'https://')):
            url = 'http://' + url
            self.url_input.setText(url)
        self.web_view.load(QUrl(url))
        self.current_url = url

    def on_load_started(self):
        self.save_text_btn.setEnabled(False)
        self.save_pdf_btn.setEnabled(False)
        self.token_label.setText("Original Tokens: Loading...")
        self.processed_token_label.setText("Processed Tokens: Loading...")
        self.content_size_label.setText("Original Content: Loading...")
        self.processed_size_label.setText("Processed Content: Loading...")
        self.update_total_tokens()

    def on_load_finished(self, ok: bool):
        if ok:
            # When loading a new page, reset use_history to False
            self.use_history = False
            
            self.save_text_btn.setEnabled(True)
            self.save_pdf_btn.setEnabled(True)
            self.web_view.page().toHtml(self.process_html_content)
        else:
            self.token_label.setText("Original Tokens: 0")
            self.processed_token_label.setText("Processed Tokens: 0")
            self.content_size_label.setText("Original Content: 0 chars")
            self.processed_size_label.setText("Processed Content: 0 chars")
            QMessageBox.critical(
                self,
                "Load Error",
                "Failed to load the page. Please check the URL or your connection."
            )

    def process_html_content(self, html: str):
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        page_title = title_match.group(1) if title_match else "Unknown Page"
        
        soup = BeautifulSoup(html, 'html.parser')
        original_text = soup.get_text(separator='\n', strip=True)
        self.original_content = original_text
        
        orig_token_count = self.count_tokens(original_text)
        
        self.token_label.setText(f"Original Tokens: {orig_token_count:,}")
        self.content_size_label.setText(f"Original Content: {len(original_text):,} chars")
        
        try:
            content = self.extract_cleaned_text(html)
            max_tokens = self.max_tokens_input.value()
            if self.count_tokens(content) > max_tokens:
                content = self.truncate_to_token_limit(content, max_tokens)
            self.current_content = content
            
            processed_token_count = self.count_tokens(content)
            self.processed_token_label.setText(f"Processed Tokens: {processed_token_count:,}")
            self.processed_size_label.setText(f"Processed Content: {len(content):,} chars")
            
            if self.offline_checkbox.isChecked():
                if self.current_url:
                    self.save_to_cache(html, self.current_url, page_title, original_text, content)
            
            self.update_total_tokens()
        except Exception as e:
            self.processed_token_label.setText(f"Processed Tokens: Error")
            self.processed_size_label.setText("Processed Content: Error")
            print(f"Error calculating tokens: {e}")

    def truncate_to_token_limit(self, text, max_tokens):
        if not text or not self.encoding:
            return text
        try:
            tokens = self.encoding.encode(text)
            if len(tokens) <= max_tokens:
                return text
            truncated_tokens = tokens[:max_tokens-10]
            truncated_text = self.encoding.decode(truncated_tokens)
            truncated_text += "\n\n[Content truncated to fit token limit]"
            return truncated_text
        except Exception as e:
            print(f"Error truncating tokens: {e}")
            return text

    def update_prompt_tokens(self):
        prompt = self.prompt_input.text()
        token_count = self.count_tokens(prompt)
        self.prompt_token_label.setText(f"Prompt tokens: {token_count}")
        self.update_total_tokens()

    def update_total_tokens(self):
        # wybór treści
        if getattr(self, 'use_original_checkbox', None) and self.use_original_checkbox.isChecked():
            content_to_count = self.original_content
        else:
            content_to_count = self.current_content

        content_tokens = self.count_tokens(content_to_count) if content_to_count else 0

        prompt_tokens = int(
            self.prompt_token_label.text().replace("Prompt tokens: ", "").replace(",", "")
        )

        # dopiero gdy use_history=True, sumujemy tokeny z historii
        if getattr(self, 'use_history', False):
            history_tokens = sum(
                self.count_tokens(f"User: {h['prompt']}\nAssistant: {h['response']}")
                for h in self.conversation_history
            )
        else:
            history_tokens = 0

        template_tokens = 20  # np. szablon/padding

        total_tokens = content_tokens + prompt_tokens + history_tokens + template_tokens
        self.total_token_label.setText(f"Total tokens: {total_tokens:,}")

    def update_token_calculations(self):
        if self.original_content:
            max_tokens = self.max_tokens_input.value()
            if self.count_tokens(self.original_content) > max_tokens:
                self.current_content = self.truncate_to_token_limit(self.original_content, max_tokens)
            else:
                self.current_content = self.original_content
            processed_token_count = self.count_tokens(self.current_content)
            self.processed_token_label.setText(f"Processed Tokens: {processed_token_count:,}")
            self.processed_size_label.setText(f"Processed Content: {len(self.current_content):,} chars")
            self.update_total_tokens()

    def on_save(self):
        # We select content based on the checkbox
        if getattr(self, 'use_original_checkbox', None) and self.use_original_checkbox.isChecked():
            text_to_save = self.original_content
        else:
            text_to_save = self.current_content

        if text_to_save:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save extracted text", "", "Text Files (*.txt)"
            )
            if not path:
                return
            with open(path, "w", encoding="utf-8") as f:
                f.write(text_to_save)
            QMessageBox.information(self, "Success", f"Text saved to:\n{path}")
        else:
            # fallback: if there is no content, get HTML and process
            self.web_view.page().toHtml(self.process_html_for_saving)

    def process_html_for_saving(self, html: str):
        try:
            content = self.extract_cleaned_text(html)
            path, _ = QFileDialog.getSaveFileName(
                self, "Save extracted text", "", "Text Files (*.txt)"
            )
            if not path:
                return
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            QMessageBox.information(self, "Success", f"Text saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def extract_cleaned_text(self, html):
        soup = BeautifulSoup(html, "html.parser")
        
        for elem in soup.find_all(["span", "sup"], class_=re.compile(r"mw-editsection|reference")):
            elem.decompose()
            
        for table in soup.find_all("table", class_=lambda c: c and ("infobox" in c or "wikitable" in c)):
            rows = ["\t".join([cell.get_text(strip=True) for cell in row.find_all(["th", "td"])])
                   for row in table.find_all("tr")]
            table.replace_with(NavigableString("\n".join(rows)))

        cleaned_html = str(soup)
        content = self.extractor.get_content(cleaned_html)
        return re.sub(r"\[\d+\]", "", content)

    def save_as_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save page as PDF", "", "PDF Files (*.pdf)"
        )
        if not path:
            return
        if not path.lower().endswith('.pdf'):
            path += '.pdf'

        def pdf_written(data):
            if data:
                try:
                    with open(path, 'wb') as f:
                        f.write(data)
                    QMessageBox.information(self, "Success", f"PDF saved to:\n{path}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to write PDF: {str(e)}")
            else:
                QMessageBox.critical(self, "Error", "Failed to generate PDF content.")

        self.web_view.page().printToPdf(pdf_written)

    def view_conversation_history(self):
        """
        Show a dialog with LLM history entries sorted by timestamp (newest first),
        allow deleting individual entries, and restore the selected conversation.
        """
        if not self.conversation_history:
            QMessageBox.information(self, "History", "No conversation history yet.")
            return

        # 1) Sort the in-memory history by timestamp descending
        sorted_history = sorted(
            self.conversation_history,
            key=lambda e: e.get('timestamp', ''),
            reverse=True
        )

        # 2) Build the dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Conversation History")
        dialog.resize(600, 400)
        layout = QVBoxLayout(dialog)

        # 3) List widget showing timestamp + prompt preview
        history_list = QListWidget(dialog)
        for entry in sorted_history:
            ts = entry.get('timestamp', 'unknown time')
            preview = entry.get('prompt', '').replace('\n', ' ')[:30]
            history_list.addItem(f"{ts} – {preview}…")
        layout.addWidget(history_list)

        # 4) Delete Selected button
        delete_btn = QPushButton("Delete Selected", dialog)
        def delete_selected():
            row = history_list.currentRow()
            if row < 0:
                return
            entry = sorted_history.pop(row)
            # remove from the master list and persist
            self.conversation_history.remove(entry)
            self.save_conversation_history()
            # remove from the UI
            history_list.takeItem(row)
        delete_btn.clicked.connect(delete_selected)
        layout.addWidget(delete_btn)

        # 5) OK / Cancel buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        # 6) Execute and, if accepted, restore the chosen item
        if dialog.exec_() == QDialog.Accepted and history_list.currentRow() >= 0:
            idx = history_list.currentRow()
            selected = sorted_history[idx]

            self.prompt_input.setText(selected['prompt'])
            self.current_content = selected.get('content', self.current_content)
            tokens = self.count_tokens(self.current_content)
            self.processed_token_label.setText(f"Processed Tokens: {tokens:,}")
            self.processed_size_label.setText(f"Processed Content: {len(self.current_content):,} chars")
            self.response_area.setPlainText(selected['response'])
            self.update_total_tokens()
            
            # Set the use_history flag to True when loading from history
            # This ensures that subsequent queries will include conversation history
            self.use_history = True

    def clear_conversation_history(self):
        if self.conversation_history:
            reply = QMessageBox.question(
                self, 'Clear History',
                'Are you sure you want to clear the conversation history?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.conversation_history = []
                self.save_conversation_history()
                self.update_total_tokens()
                QMessageBox.information(self, "History", "Conversation history cleared.")
        else:
            QMessageBox.information(self, "History", "No conversation history to clear.")

    def save_conversation_history(self):
        history_file = os.path.join(self.web_history_dir, "history.json")
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)

    def start_llm_query(self):
        prompt = self.prompt_input.text().strip()
        if not prompt:
            QMessageBox.warning(self, "Warning", "Please enter a prompt.")
            return

        self.send_btn.setEnabled(False)
        self.response_area.setPlainText("Processing…")

        if self.current_content:
            # choose original or processed content
            content_to_send = (
                self.original_content if self.use_original_checkbox.isChecked()
                else self.current_content
            )
            self.process_llm_with_content(prompt, content_to_send, use_history=self.use_history)
        else:
            # no page → clean chat
            self.web_view.page().toHtml(self.process_for_llm)

    def process_for_llm(self, html: str):
        try:
            # Save the raw content of the page
            soup = BeautifulSoup(html, 'html.parser')
            original_text = soup.get_text(separator='\n', strip=True)
            self.original_content = original_text

            # Process the text and trim if necessary
            content = self.extract_cleaned_text(html)
            max_tokens = self.max_tokens_input.value()
            if self.count_tokens(content) > max_tokens:
                content = self.truncate_to_token_limit(content, max_tokens)
            self.current_content = content

            # choice of original or processed content
            content_to_send = (
                self.original_content if self.use_original_checkbox.isChecked()
                else self.current_content
            )

            self.process_llm_with_content(
                self.prompt_input.text(), content_to_send, use_history=self.use_history
            )
        except Exception as e:
            self.send_btn.setEnabled(True)
            QMessageBox.critical(self, "Error", str(e))

    def process_llm_with_content(self, prompt, content, use_history=False):
        """
        Kick off an LLM query using either history+content or content only.
        """
        self.use_history = use_history
        try:
            # For web browsing, we DON'T use history
            history = self.conversation_history if use_history else []

            # Build prompt for LLM - changed order: content first, user prompt second
            combined_prompt = f"Web Content:\n{content}\n\nUser: {prompt}"

            self.llm_worker = LLMWorker(combined_prompt, "", history)
            self.llm_worker.finished.connect(self.handle_llm_response)
            self.llm_worker.error.connect(self.handle_llm_error)
            self.llm_worker.start()
        except Exception as e:
            self.send_btn.setEnabled(True)
            QMessageBox.critical(self, "Error", str(e))

    def handle_llm_response(self, response):
        """
        Display the response and always record it in history
        (even if it was a page‐query, so you can re‐use it later).
        """
        self.response_area.setPlainText(response)
        self.send_btn.setEnabled(True)

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.conversation_history.append({
            'timestamp': timestamp,
            'prompt':    self.prompt_input.text(),
            'content':   self.current_content,
            'response':  response
        })
        self.save_conversation_history()
        self.update_total_tokens()

    def handle_llm_error(self, error_msg):
        QMessageBox.critical(self, "LLM Error", error_msg)
        self.send_btn.setEnabled(True)

    def preview_prompt(self):
        if not self.current_content and not self.original_content:
            QMessageBox.warning(self, "Warning", "No content loaded.")
            return
        prompt = self.prompt_input.text().strip()
        if not prompt:
            QMessageBox.warning(self, "Warning", "Please enter a prompt.")
            return

        # select content to preview
        content_to_show = (
            self.original_content if self.use_original_checkbox.isChecked()
            else self.current_content
        )
        full_prompt = f"Web Content:\n{content_to_show}\n\nUser: {prompt}"

        dialog = QDialog(self)
        dialog.setWindowTitle("Preview Prompt")
        dialog.resize(600, 400)
        layout = QVBoxLayout(dialog)

        # search box
        search_input = QLineEdit()
        search_input.setPlaceholderText("Search in content...")
        layout.addWidget(search_input)

        # editable text field
        text_edit = QPlainTextEdit()
        text_edit.setPlainText(full_prompt)
        layout.addWidget(text_edit)

        # token hint
        token_label = QLabel(f"Total tokens: {self.count_tokens(full_prompt):,}")
        layout.addWidget(token_label)

        # OK/Cancel buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        # highlighting/matching function
        def on_search(text):
            cursor = text_edit.textCursor()
            cursor.movePosition(QTextCursor.Start)
            text_edit.setTextCursor(cursor)
            if text:
                text_edit.find(text)
        search_input.textChanged.connect(on_search)

        if dialog.exec_() == QDialog.Accepted:
            # update prompt based on edits
            edited = text_edit.toPlainText().split('\nUser: ', 1)
            if len(edited) > 1:
                self.prompt_input.setText(edited[1].strip())
            self.update_prompt_tokens()

    def edit_content(self):
        # we select the text to edit
        if getattr(self, 'use_original_checkbox', None) and self.use_original_checkbox.isChecked():
            text = self.original_content
        else:
            text = self.current_content

        if not text:
            QMessageBox.warning(self, "Warning", "No content to edit.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Content")
        dialog.resize(600, 400)
        layout = QVBoxLayout(dialog)

        # search box
        search_input = QLineEdit()
        search_input.setPlaceholderText("Search in content...")
        layout.addWidget(search_input)

        # editable text field
        text_edit = QPlainTextEdit()
        text_edit.setPlainText(text)
        layout.addWidget(text_edit)

        # token hint
        token_label = QLabel(f"Tokens: {self.count_tokens(text):,}")
        layout.addWidget(token_label)

        # OK/Cancel buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        # search function
        def on_search(text):
            cursor = text_edit.textCursor()
            cursor.movePosition(QTextCursor.Start)
            text_edit.setTextCursor(cursor)
            if text:
                text_edit.find(text)
        search_input.textChanged.connect(on_search)

        if dialog.exec_() == QDialog.Accepted:
            new_text = text_edit.toPlainText()
            if self.use_original_checkbox.isChecked():
                self.original_content = new_text
            else:
                self.current_content = new_text
            # refresh counters
            self.processed_token_label.setText(
                f"Processed Tokens: {self.count_tokens(self.current_content):,}"
            )
            self.processed_size_label.setText(
                f"Processed Content: {len(self.current_content):,} chars"
            )
            self.update_total_tokens()

    def on_extractor_changed(self, name: str):
        """
        Ustawia self.extractor według wyboru użytkownika.
        Jeśli strona jest już załadowana, przetwarza ją ponownie.
        """
        cls = getattr(extractors, name, None)
        if cls is None:
            QMessageBox.warning(self, "Extractor Error", f"Nieznany extractor: {name}")
            return

        # Tworzymy nowego extractora (możesz dostosować parametry, np. raise_on_failure)
        try:
            self.extractor = cls()
        except TypeError:
            # Niektóre extractory mogą mieć inne sygnatury
            self.extractor = cls(raise_on_failure=False)

        # Jeśli mamy już załadowaną stronę – przetwarzamy ją ponownie
        if self.current_url:
            self.web_view.page().toHtml(self.process_html_content)

    def closeEvent(self, event):
        page = self.web_view.page()
        self.web_view.setPage(None)

        page.deleteLater()
        self.web_profile.deleteLater()

        super().closeEvent(event)

    def _clear_find_highlight(self):
        # clears _any_ existing highlights
        self.web_view.page().findText("", QWebEnginePage.FindFlags())

    def open_find_dialog(self):
        # 1) Ask for term
        term, ok = QInputDialog.getText(self, "Find on page", "Search for:")
        if not ok or not term:
            return

        # 2) Clear _before_ searching
        self.web_view.page().findText("", QWebEnginePage.FindFlags())

        # 3) Find forward
        self.web_view.page().findText(term, QWebEnginePage.FindFlags())

if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())