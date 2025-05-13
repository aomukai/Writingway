from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit, QPushButton,
    QTextBrowser, QLabel, QApplication, QSplitter, QWidget, QShortcut,
    QAction, QMenuBar, QMessageBox, QListWidget, QListWidgetItem, QMenu, QInputDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QPoint
from PyQt5.QtGui import QPixmap, QKeySequence, QPalette, QColor, QDesktopServices
from urllib.parse import urlparse, unquote 
import wikipediaapi
import requests
import json
import os
from io import BytesIO
from settings.llm_api_aggregator import WWApiAggregator
from util.find_dialog import FindDialog

class LLMThread(QThread):
    response_signal = pyqtSignal(str)

    def __init__(self, prompt, overrides):
        super().__init__()
        self.prompt = prompt
        self.overrides = overrides

    def run(self):
        try:
            response = WWApiAggregator.send_prompt_to_llm(self.prompt, self.overrides)
            self.response_signal.emit(response if response else "LLM did not return a response.")
        except Exception as e:
            self.response_signal.emit(f"Error sending prompt: {e}")

class HistoryDialog(QDialog):
    def __init__(self, parent=None, history=None):
        super().__init__(parent)
        self.parent = parent
        self.history = history or []
        self.setWindowTitle("Search History")
        self.setGeometry(200, 200, 600, 400)
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Search field for filtering
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Filter history...")
        self.search_field.textChanged.connect(self.filter_history)
        layout.addWidget(self.search_field)
        
        # History list with custom context menu
        self.history_list = QListWidget()
        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self.show_context_menu)
        self.history_list.itemDoubleClicked.connect(self.load_article)
        layout.addWidget(self.history_list)
        
        # Populate the list
        self.populate_history_list()
        
        self.setLayout(layout)
    
    def populate_history_list(self):
        self.history_list.clear()
        for query, unused in self.history:
            item = QListWidgetItem(query)
            self.history_list.addItem(item)
    
    def filter_history(self):
        filter_text = self.search_field.text().lower()
        self.history_list.clear()
        for query, unused in self.history:
            if filter_text in query.lower():
                item = QListWidgetItem(query)
                self.history_list.addItem(item)
    
    def show_context_menu(self, pos: QPoint):
        item = self.history_list.itemAt(pos)
        if item is None:
            return
        menu = QMenu()
        delete_action = QAction("Delete", self)
        rename_action = QAction("Rename", self)
        menu.addAction(delete_action)
        menu.addAction(rename_action)
        delete_action.triggered.connect(lambda: self.delete_item(item))
        rename_action.triggered.connect(lambda: self.rename_item(item))
        menu.exec_(self.history_list.mapToGlobal(pos))
    
    def delete_item(self, item: QListWidgetItem):
        query = item.text()
        self.history = [(q, art) for q, art in self.history if q.lower() != query.lower()]
        self.parent.search_history = self.history
        self.parent.save_history()
        self.populate_history_list()
    
    def rename_item(self, item: QListWidgetItem):
        old_query = item.text()
        new_query, ok = QInputDialog.getText(self, "Rename Article", "Enter new title:", text=old_query)
        if ok and new_query.strip():
            new_query = new_query.strip()
            for index, (q, art) in enumerate(self.history):
                if q.lower() == old_query.lower():
                    self.history[index] = (new_query, art)
                    break
            self.parent.search_history = self.history
            self.parent.save_history()
            self.populate_history_list()
    
    def load_article(self, item: QListWidgetItem):
        # Load a saved article from history
        query = item.text()
        for q, article in self.history:
            if q.lower() == query.lower():
                self.parent.search_field.setText(query)
                self.parent.full_article_text = article
                self.parent.display_history_article(update_history=True, mode="saved")
                self.close()
                break

class WikidataDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Wikipedia Search and LLM Processor")
        self.setGeometry(100, 100, 1000, 800)
        
        # Set window flags 
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setWindowModality(Qt.NonModal)

        # Initialize search and article history
        self.search_history = []  # Persistent history of saved articles
        self.article_history = []  # Session browsing history
        self.current_article_index = -1
        
        # History file path
        self.history_file = "assets/wiki_history.json"
        self.load_history()

        # Default Wikipedia API instance (English)
        self.wiki_wiki = wikipediaapi.Wikipedia(
            language='en',
            user_agent='WritingwayApp/1.0 (contact@example.com)',
            extract_format=wikipediaapi.ExtractFormat.WIKI
        )

        # Main layout
        main_layout = QVBoxLayout(self)
        
        self.create_menu_bar()
        
        # Top bar: Navigation and action buttons
        top_bar_layout = QHBoxLayout()
        
        self.back_button = QPushButton("<")
        self.back_button.setMaximumWidth(30)
        self.back_button.clicked.connect(self.go_back)
        self.back_button.setEnabled(False)
        top_bar_layout.addWidget(self.back_button)
        
        self.forward_button = QPushButton(">")
        self.forward_button.setMaximumWidth(30)
        self.forward_button.clicked.connect(self.go_forward)
        self.forward_button.setEnabled(False)
        top_bar_layout.addWidget(self.forward_button)
        
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Enter search term...")
        top_bar_layout.addWidget(self.search_field)
        
        self.language_input = QLineEdit()
        self.language_input.setPlaceholderText("Enter language code...")
        self.language_input.setText("en")
        self.language_input.setMaximumWidth(50)
        top_bar_layout.addWidget(self.language_input)
        
        self.search_button = QPushButton("Search Wikipedia")
        self.search_button.clicked.connect(lambda: self.perform_search(update_history=True))
        top_bar_layout.addWidget(self.search_button)
        
        self.expand_button = QPushButton("Show Full Article")
        self.expand_button.clicked.connect(self.show_full_article)
        self.expand_button.setEnabled(False)
        top_bar_layout.addWidget(self.expand_button)
        
        self.edit_button = QPushButton("Edit Article")
        self.edit_button.clicked.connect(self.edit_article)
        self.edit_button.setEnabled(False)
        top_bar_layout.addWidget(self.edit_button)
        
        self.save_button = QPushButton("Save Article")
        self.save_button.clicked.connect(self.save_article)
        self.save_button.setEnabled(False)
        top_bar_layout.addWidget(self.save_button)
        
        self.shortcut_find = QShortcut(QKeySequence("Ctrl+F"), self)
        self.shortcut_find.activated.connect(self.open_find_dialog)
        self.find_dialog = None

        main_layout.addLayout(top_bar_layout)

        # Main vertical splitter
        self.main_splitter = QSplitter(Qt.Vertical)

        # Top section: Article image and text
        self.wiki_splitter = QSplitter(Qt.Vertical)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMaximumHeight(300)
        self.image_label.setScaledContents(False)
        self.wiki_splitter.addWidget(self.image_label)
        
        self.result_display = QTextBrowser()
        self.result_display.setOpenExternalLinks(False)
        self.wiki_splitter.addWidget(self.result_display)
        self.result_display.anchorClicked.connect(self.handle_link_click)
        
        palette = self.result_display.palette()
        palette.setColor(QPalette.Inactive, QPalette.Highlight, QColor("yellow"))
        palette.setColor(QPalette.Inactive, QPalette.HighlightedText, QColor("black"))
        self.result_display.setPalette(palette)
        
        self.wiki_splitter.setStretchFactor(0, 1)
        self.wiki_splitter.setStretchFactor(1, 3)
        self.main_splitter.addWidget(self.wiki_splitter)

        # Bottom section: LLM Processing
        self.llm_widget = QWidget()
        llm_layout = QHBoxLayout(self.llm_widget)
        
        prompt_layout = QVBoxLayout()
        prompt_label = QLabel("Enter prompt:")
        prompt_layout.addWidget(prompt_label)
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("Remember to set the maximum timeout in the settings and the number of tokens...")
        prompt_layout.addWidget(self.prompt_input)
        self.send_button = QPushButton("Send Message")
        self.send_button.clicked.connect(self.send_message)
        prompt_layout.addWidget(self.send_button)
        llm_layout.addLayout(prompt_layout)
        
        answer_layout = QVBoxLayout()
        answer_label = QLabel("LLM Response:")
        answer_layout.addWidget(answer_label)
        self.answer_display = QTextBrowser()
        answer_layout.addWidget(self.answer_display)
        llm_layout.addLayout(answer_layout)
        
        self.main_splitter.addWidget(self.llm_widget)
        self.main_splitter.setStretchFactor(0, 4)
        self.main_splitter.setStretchFactor(1, 1)
        main_layout.addWidget(self.main_splitter)

        self.full_article_text = ""

        self.setLayout(main_layout)
    
    def create_menu_bar(self):
        menu_bar = QMenuBar(self)
        
        history_menu = menu_bar.addMenu("History")
        show_history_action = QAction("Show History", self)
        show_history_action.triggered.connect(self.show_history)
        history_menu.addAction(show_history_action)
        clear_history_action = QAction("Clear History", self)
        clear_history_action.triggered.connect(self.clear_history)
        history_menu.addAction(clear_history_action)
        
        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_app_info)
        help_menu.addAction(about_action)
        
        self.layout().setMenuBar(menu_bar)
    
    def show_history(self):
        history_dialog = HistoryDialog(self, self.search_history)
        history_dialog.exec_()
    
    def clear_history(self):
        reply = QMessageBox.question(
            self, "Clear History",
            "Are you sure you want to clear the search history?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.search_history = []
            self.save_history()
            QMessageBox.information(self, "History Cleared", "Search history has been cleared.")
    
    def show_app_info(self):
        about_text = """
        <h2>Wikipedia Search and LLM Processor</h2>
        <p>This application allows you to search Wikipedia articles and process them using a Language Model.</p>
        <h3>Features:</h3>
        <ul>
            <li>Search Wikipedia articles in multiple languages</li>
            <li>View article summaries, images, and full articles</li>
            <li>Track, delete, and rename articles in search history</li>
            <li>Edit and save articles directly in the app</li>
            <li>Process article text with LLM</li>
        </ul>
        <h3>Usage:</h3>
        <ul>
            <li>Enter a search term and select a language code (default: en)</li>
            <li>Click "Search Wikipedia" to load the article</li>
            <li>Click "Show Full Article" to view a longer version</li>
            <li>Right-click history items to Delete or Rename them</li>
            <li>Click "Edit Article" to modify the full text</li>
            <li>Click "Save Article" to save changes</li>
            <li>Use Ctrl+F to search within the article</li>
        </ul>
        """
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("About")
        msg_box.setText(about_text)
        msg_box.setTextFormat(Qt.RichText)
        msg_box.exec_()
    
    def load_history(self):
        # Load the persistent search history from file
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.search_history = json.load(f)
        except Exception as e:
            print(f"Error loading history: {e}")
    
    def save_history(self):
        # Save the persistent search history to file
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.search_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving history: {e}")
    
    def go_back(self):
        if self.current_article_index > 0:
            self.current_article_index -= 1
            entry = self.article_history[self.current_article_index]
            self.search_field.setText(entry["title"])
            if entry["mode"] == "search":
                self.perform_search(update_history=False)
            elif entry["mode"] == "saved":
                self.full_article_text = entry["content"]
                self.display_history_article(update_history=False)
            self.update_navigation_buttons()
            self.result_display.repaint()
            self.image_label.repaint()
    
    def go_forward(self):
        if self.current_article_index < len(self.article_history) - 1:
            self.current_article_index += 1
            entry = self.article_history[self.current_article_index]
            self.search_field.setText(entry["title"])
            if entry["mode"] == "search":
                self.perform_search(update_history=False)
            elif entry["mode"] == "saved":
                self.full_article_text = entry["content"]
                self.display_history_article(update_history=False)
            self.update_navigation_buttons()
            self.result_display.repaint()
            self.image_label.repaint()
    
    def update_navigation_buttons(self):
        self.back_button.setEnabled(self.current_article_index > 0)
        self.forward_button.setEnabled(self.current_article_index < len(self.article_history) - 1)

    def perform_search(self, update_history=True):
        # Perform a Wikipedia search and display the result
        query = self.search_field.text().strip()
        selected_language = self.language_input.text().strip() or "en"
        if not query:
            self.result_display.clear()
            self.image_label.clear()
            self.expand_button.setEnabled(False)
            self.edit_button.setEnabled(False)
            self.save_button.setEnabled(False)
            return

        wiki_wiki = wikipediaapi.Wikipedia(
            language=selected_language,
            user_agent='WritingwayApp/1.0 (contact@example.com)',
            extract_format=wikipediaapi.ExtractFormat.WIKI
        )
        try:
            page = wiki_wiki.page(query)
            if not page.exists():
                raise Exception("Article not found online.")
        except Exception as e:
            for q, article in self.search_history:
                if q.lower() == query.lower():
                    self.full_article_text = article
                    self.result_display.setHtml(article.replace('\n', '<br>'))
                    self.expand_button.setEnabled(False)
                    self.edit_button.setEnabled(True)
                    QMessageBox.information(self, "Offline Mode", "No internet connection, loaded article from history.")
                    return
            self.result_display.setPlainText("Article not found and no offline version available.")
            self.image_label.clear()
            self.expand_button.setEnabled(False)
            self.edit_button.setEnabled(False)
            self.save_button.setEnabled(False)
            return

        processed_text = page.text[:5000].replace('\n', '<br>')
        sections = self.get_sections(page)
        categories = self.get_categories(page)
        links = self.get_links(page)
        self.full_article_text = page.text

        html_links = []
        for link_title in links[:10]:
            encoded_title = link_title.replace(' ', '_')
            encoded_title = requests.utils.quote(encoded_title)
            wikipedia_url = f"https://{selected_language}.wikipedia.org/wiki/{encoded_title}"
            html_links.append(f'<li><a href="{wikipedia_url}">{link_title}</a></li>')

        html_content = f"""
        <h1>{page.title}</h1>
        <h2>Basic Information</h2>
        <p>{processed_text} [...]</p>
        <h2>Main Sections</h2>
        <ul>
            {''.join(f'<li>{section}</li>' for section in sections)}
        </ul>
        <h2>Categories</h2>
        <p>{', '.join(categories)}</p>
        <h2>Important Links</h2>
        <ul>
            {''.join(html_links)}
        </ul>
        <p><i>Showing first 5000 characters. Full article has {len(page.text):,} characters.</i></p>
        """
    
        self.result_display.setHtml(html_content)
        try:
            image_url = self.get_page_image(page.title, selected_language)
            if image_url:
                response = requests.get(image_url)
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                if pixmap.height() > 300:
                    pixmap = pixmap.scaledToHeight(300, Qt.SmoothTransformation)
                self.image_label.setPixmap(pixmap)
            else:
                self.image_label.clear()
        except Exception as e:
            self.image_label.clear()

        self.expand_button.setEnabled(True)
        self.edit_button.setEnabled(True)
        self.save_button.setEnabled(False)
                
        # Add to persistent search history only if the query doesn't exist (case-insensitive)
        if not any(q.lower() == query.lower() for q, unused in self.search_history):
            self.search_history.append((query, self.full_article_text))
            self.save_history()
        
        # Update browsing history if this is a new navigation event
        if update_history:
            if self.current_article_index == -1 or (self.article_history and self.article_history[self.current_article_index]["title"] != page.title):
                if self.current_article_index < len(self.article_history) - 1:
                    self.article_history = self.article_history[:self.current_article_index + 1]
                self.article_history.append({
                    "title": page.title,
                    "mode": "search"
                })
                self.current_article_index = len(self.article_history) - 1
                self.update_navigation_buttons()

    def display_history_article(self, update_history=True, mode="saved"):
        # Display a saved article from history
        self.image_label.clear()
        html_content = self.full_article_text.replace('\n', '<br>')
        self.result_display.setHtml(html_content)
        self.expand_button.setEnabled(False)
        self.edit_button.setEnabled(True)
        self.save_button.setEnabled(False)
        self.result_display.setReadOnly(True)
        if update_history:
            if self.current_article_index == -1 or (self.article_history and self.article_history[self.current_article_index]["title"] != self.search_field.text().strip()):
                if self.current_article_index < len(self.article_history) - 1:
                    self.article_history = self.article_history[:self.current_article_index + 1]
                self.article_history.append({
                    "title": self.search_field.text().strip(),
                    "mode": mode,
                    "content": self.full_article_text
                })
                self.current_article_index = len(self.article_history) - 1
                self.update_navigation_buttons()

    def handle_link_click(self, url):
        url_str = url.toString()
        parsed_url = urlparse(url_str)
        if parsed_url.hostname and parsed_url.hostname.endswith('.wikipedia.org'):
            try:
                lang = parsed_url.hostname.split('.')[0]
                title_encoded = parsed_url.path.split('/wiki/')[-1]
                title = unquote(title_encoded.replace('_', ' '))
                self.language_input.setText(lang)
                self.search_field.setText(title)
                self.perform_search(update_history=True)
            except Exception as e:
                print(f"Error processing Wikipedia link: {e}")
        else:
            QDesktopServices.openUrl(url)

    def show_full_article(self):
        # Show the full article text
        html_content = self.full_article_text.replace('\n', '<br>')
        self.result_display.setHtml(html_content)
        self.result_display.setReadOnly(True)
    
    def edit_article(self):
        # Enable editing of the full article
        self.show_full_article()
        self.result_display.setReadOnly(False)
        self.save_button.setEnabled(True)
    
    def save_article(self):
        # Save the edited article to search history
        edited_text = self.result_display.toPlainText()
        self.full_article_text = edited_text
        query = self.search_field.text().strip()
        updated = False
        for index, (q, _) in enumerate(self.search_history):
            if q.lower() == query.lower():
                self.search_history[index] = (q, edited_text)
                updated = True
                break
        if updated:
            self.save_history()
            QMessageBox.information(self, "Article Saved", "The article has been updated in the history.")
        else:
            QMessageBox.warning(self, "Save Error", "The current article was not found in history to update.")
        self.result_display.setReadOnly(True)
        self.save_button.setEnabled(False)

    def get_page_image(self, title, language):
        # Fetch the article's thumbnail image
        try:
            url = f"https://{language}.wikipedia.org/w/api.php?action=query&titles={title}&prop=pageimages&format=json&pithumbsize=800"
            response = requests.get(url)
            data = response.json()
            pages = data['query']['pages']
            page_id = next(iter(pages))
            return pages[page_id].get('thumbnail', {}).get('source')
        except Exception as e:
            print(f"Error fetching image: {e}")
            return None

    def get_sections(self, page):
        return [s.title for s in page.sections if s.level == 2][:10]

    def get_categories(self, page):
        return [c.split(':')[-1] for c in page.categories.keys()][:15]

    def get_links(self, page):
        return [link for link in page.links.keys()][:20]

    def send_message(self):
        # Send prompt to LLM
        user_prompt = self.prompt_input.toPlainText().strip()
        if not user_prompt:
            self.answer_display.setPlainText("Please enter prompt.")
            return

        if getattr(self, 'llm_thread_running', False):
            return
        self.llm_thread_running = True

        final_prompt = f"{self.full_article_text}\n\n{user_prompt}"
        self.answer_display.setPlainText("Sending messages to LLM. Please be patient as it may take a while.")
        self.send_button.setEnabled(False)

        overrides = {
            "provider": "Local",
            "model": "Local Model",
            "max_tokens": 128000,
            "temperature": 1.0
        }

        self.llm_thread = LLMThread(final_prompt, overrides)
        self.llm_thread.response_signal.connect(self.update_llm_response)
        self.llm_thread.start()

    def update_llm_response(self, response):
        self.answer_display.setPlainText(response)
        self.send_button.setEnabled(True)
        self.llm_thread_running = False

    def open_find_dialog(self):
        if self.find_dialog is None:
            self.find_dialog = FindDialog(self.result_display, self)
        self.find_dialog.show()
        self.find_dialog.raise_()
        self.find_dialog.search_field.setFocus()

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = WikidataDialog()
    window.show()
    sys.exit(app.exec_())