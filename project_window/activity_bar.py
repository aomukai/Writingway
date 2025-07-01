from PyQt5.QtWidgets import QToolBar, QAction, QWidget, QVBoxLayout
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt
from settings.theme_manager import ThemeManager
from gettext import gettext as _

class ActivityBar(QWidget):
    """Vertical icon panel for switching between views, similar to VS Code Activity Bar."""
    def __init__(self, controller, tint_color=QColor("black"), position="left"):
        super().__init__()
        self.controller = controller  # Reference to ProjectWindow
        self.tint_color = tint_color
        self.position = position  # 'left' or 'right' for future feature
        self.current_view = None
        self.toolbar = QToolBar("Activity Bar")
        self.toolbar.setObjectName("ActivityBar")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(self.toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        self.toolbar.setStyleSheet("QToolBar#ActivityBar { border: 0px; }")
        self.toolbar.setOrientation(Qt.Vertical)
        self.toolbar.setFixedWidth(50)  # Fixed width for icons

        # Actions
        self.outline_action = self.add_action(
            "assets/icons/pen-tool.svg", 
            _("Outline and Scene Editor"), 
            self.controller.toggle_outline_view
        )
        self.search_action = self.add_action(
            "assets/icons/search.svg", 
            _("Search and Replace"), 
            self.controller.toggle_search_view
        )
        self.compendium_action = self.add_action(
            "assets/icons/book-open.svg", 
            _("Compendium"), 
            self.controller.toggle_compendium_view
        )
        self.prompts_action = self.add_action(
            "assets/icons/ai-script-icon.svg",
            _("Prompt Options"),
            self.controller.toggle_prompts_view
        )
        self.content_view_action = self.add_action(
            "assets/icons/activity.svg",
            _("Content View"),
            self.controller.toggle_content_view
        )

        # Set initial state
        self.outline_action.setChecked(True)
        self.current_view = "outline"

    def add_action(self, icon_path, tooltip, callback):
        action = QAction(ThemeManager.get_tinted_icon(icon_path, self.tint_color), "", self)
        action.setToolTip(tooltip)
        action.setCheckable(True)
        action.triggered.connect(lambda: self.handle_action(action, callback))
        self.toolbar.addAction(action)
        return action

    def handle_action(self, action, callback):
        """Handle action clicks, ensuring only one is checked and toggling sidebar."""
        self.controller.clear_search_highlights()  # Clear search highlights
        if action.isChecked():
            # Uncheck other actions
            for act in [self.outline_action, self.search_action, self.compendium_action, self.prompts_action, self.content_view_action]:
                if act != action:
                    act.setChecked(False)
            # Set current view
            view_map = {
                self.outline_action: "outline",
                self.search_action: "search",
                self.compendium_action: "compendium",
                self.prompts_action: "prompts",
                self.content_view_action: "content_view"
            }
            self.current_view = view_map.get(action)
            callback(True)  # Show the view
        else:
            action.setChecked(False)
            callback(False)  # Hide the view
            self.current_view = None

    def update_tint(self, tint_color):
        """Update icon tints when theme changes."""
        self.tint_color = tint_color
        self.outline_action.setIcon(ThemeManager.get_tinted_icon("assets/icons/pen-tool.svg", tint_color))
        self.search_action.setIcon(ThemeManager.get_tinted_icon("assets/icons/search.svg", tint_color))
        self.compendium_action.setIcon(ThemeManager.get_tinted_icon("assets/icons/book-open.svg", tint_color))
        self.prompts_action.setIcon(ThemeManager.get_tinted_icon("assets/icons/ai-script-icon.svg", tint_color))
        self.content_view_action.setIcon(ThemeManager.get_tinted_icon("assets/icons/activity.svg", tint_color))
