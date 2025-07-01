from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QLabel,
    QShortcut,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence


from .global_toolbar import GlobalToolbar
from .activity_bar import ActivityBar
from .scene_editor import SceneEditor
from .content_view_widget import ContentViewWidget
from .project_tree_widget import ProjectTreeWidget
from .search_replace_panel import SearchReplacePanel
from compendium.compendium_panel import CompendiumPanel
from .embedded_prompts_panel import EmbeddedPromptsPanel
from .bottom_stack import BottomStack

try:
    from gettext import gettext as _
except ImportError:
    def _(s):
        return s


def init_ui(self):
    self.setWindowTitle(_("Project: {}").format(self.model.project_name))
    self.resize(900, 600)

    self.setup_status_bar()

    self.global_toolbar = GlobalToolbar(self, self.icon_tint)
    self.addToolBar(self.global_toolbar.toolbar)

    main_widget = QWidget()
    main_layout = QHBoxLayout(main_widget)
    main_layout.setContentsMargins(0, 0, 0, 0)

    self.main_splitter = QSplitter(Qt.Horizontal)
    main_layout.addWidget(self.main_splitter)

    # Left side: Activity Bar + Side Bar
    self.left_widget = QWidget()
    left_layout = QHBoxLayout(self.left_widget)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(0)

    self.activity_bar = ActivityBar(self, self.icon_tint, position="left")
    left_layout.addWidget(self.activity_bar)
    self.scene_editor = SceneEditor(self, self.icon_tint)

    self.content_view_panel = ContentViewWidget(self.model)
    self.content_view_panel.content_changed.connect(self.on_content_view_changed)

    self.side_bar = QStackedWidget()
    self.side_bar.setMinimumWidth(200)
    self.project_tree = ProjectTreeWidget(self, self.model)
    self.search_panel = SearchReplacePanel(self, self.model, self.icon_tint)
    self.compendium_panel = CompendiumPanel(self, enhanced_window=self.enhanced_window)
    self.prompts_panel = EmbeddedPromptsPanel(self.model.project_name, self)
    self.side_bar.addWidget(self.project_tree)
    self.side_bar.addWidget(self.search_panel)
    self.side_bar.addWidget(self.compendium_panel)
    self.side_bar.addWidget(self.prompts_panel)
    self.side_bar.addWidget(self.content_view_panel)
    left_layout.addWidget(self.side_bar)

    self.main_splitter.addWidget(self.left_widget)

    right_vertical_splitter = QSplitter(Qt.Vertical)
    self.compendium_editor = QTextEdit()
    self.compendium_editor.setReadOnly(True)
    self.compendium_editor.setPlaceholderText(_("Select a compendium entry to view..."))
    self.prompts_editor = self.prompts_panel.editor_widget
    self.editor_stack = QStackedWidget()
    self.editor_stack.addWidget(self.scene_editor)
    self.editor_stack.addWidget(self.compendium_editor)
    self.editor_stack.addWidget(self.prompts_editor)
    self.bottom_stack = BottomStack(self, self.model, self.icon_tint)
    self.bottom_stack.preview_text.textChanged.connect(self.on_preview_text_changed)

    right_vertical_splitter.addWidget(self.editor_stack)
    right_vertical_splitter.addWidget(self.bottom_stack)
    right_vertical_splitter.setStretchFactor(0, 3)
    right_vertical_splitter.setStretchFactor(1, 1)

    self.main_splitter.addWidget(right_vertical_splitter)
    self.main_splitter.setStretchFactor(0, 1)
    self.main_splitter.setStretchFactor(1, 3)
    self.main_splitter.setHandleWidth(10)
    self.main_splitter.splitterMoved.connect(self.update_sidebar_width)
    self.setCentralWidget(main_widget)


def setup_status_bar(self):
    self.setStatusBar(self.statusBar())
    self.word_count_label = QLabel(_("Words: {}").format(0))
    self.last_save_label = QLabel(_("Last Saved: {}").format("Never"))
    self.statusBar().addPermanentWidget(self.word_count_label)
    self.statusBar().addPermanentWidget(self.last_save_label)


def setup_connections(self):
    self.focus_mode_shortcut = QShortcut(QKeySequence("F11"), self)
    self.focus_mode_shortcut.activated.connect(self.open_focus_mode)
