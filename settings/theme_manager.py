from PyQt5.QtCore import Qt, QSize, QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon, QColor, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer
from .settings_manager import WWSettingsManager


class ThemeManager(QObject):
    """
    A simple manager for predefined themes.

    Provides methods to:
      - List available themes.
      - Retrieve a stylesheet for a given theme.
      - Apply a theme to a specific widget or the entire application.
      - Generate tinted SVG icons using QSvgRenderer.
    """
    
    # Signal emitted when theme changes
    themeChanged = pyqtSignal(str)
    
    _instance = None
    _icon_cache = {}  # Cache: (file_path, tint_color) -> QIcon

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ThemeManager, cls).__new__(cls)
            # Initialize the QObject part
            cls._instance.__init_signals()
        return cls._instance
    
    def __init_signals(self):
        # This ensures the QObject is properly initialized
        super().__init__()

    # CSS themes with glassmorphism and neumorphism effects
    THEMES = {
                "Standard": """
            QTreeWidgetItem[is-category="true"] {
                background-color: #e0e0e0; /* Fallback; will be overridden programmatically */
                font-weight: bold;
            }        
        """,
        "Night Mode": """
            /* Night Mode styling */
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                font-family: Arial, sans-serif;
            }
            QTreeWidgetItem[is-category="true"] {
            background-color: #424242;
            font-weight: bold;
            }
            QLineEdit, QTextEdit {
                background-color: #3c3f41;
                color: #ffffff;
                border: 1px solid #555;
            }
            QPushButton {
                background-color: #333;
                color: #ffffff;
                border: 2px solid #ffffff;
                padding: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #444;
            }
            QTreeView, QTreeWidget {
                background-color: #3c3f41;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #3c3f41;
                color: #ffffff;
                padding: 4px;
            }
            QTabWidget::pane {
                border: none;
            }
            QTabBar::tab {
                background: #3c3f41;
                color: #ffffff;
                padding: 5px;
            }
            QTabBar::tab:selected {
                background: #555;
            }
            QToolBar {
                background-color: #2b2b2b; /* Match QWidget background */
                border: none;
                padding: 2px;
            }
            QToolBar::separator {
                background: #555;
                width: 1px;
            }
            QToolButton {
                background-color: #2b2b2b; /* Match toolbar background */
                border: none;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: #444; /* Match QPushButton hover */
            }
            QToolButton:pressed {
                background-color: #555;
            }
        """,
        "Solarized Dark": """
            QWidget {
                background-color: #002b36;
                color: #839496;
                font-family: Arial, sans-serif;
            }
            QTreeWidgetItem[is-category="true"] {
            background-color: #073642;
            font-weight: bold;
        }
            QLineEdit, QTextEdit {
                background-color: #073642;
                color: #93a1a1;
                border: 1px solid #586e75;
            }
            QPushButton {
                background-color: #586e75;
                color: #fdf6e3;
                border: 2px solid #fdf6e3;
                padding: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #657b83;
            }
            QTreeView, QTreeWidget {
                background-color: #073642;
                color: #839496;
            }
            QHeaderView::section {
                background-color: #073642;
                color: #93a1a1;
                padding: 4px;
            }
            QTabBar::tab {
                background: #073642;
                color: #839496;
                padding: 5px;
            }
            QTabBar::tab:selected {
                background: #586e75;
            }
            QToolBar {
                background-color: #002b36; /* Match QWidget background */
                border: none;
                padding: 2px;
            }
            QToolBar::separator {
                background: #555;
                width: 1px;
            }
            QToolButton {
                background-color: #002b36; /* Match toolbar background */
                border: none;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: #657b83; /* Match QPushButton hover */
            }
            QToolButton:pressed {
                background-color: #586e75;
            }
        """,
        "Paper White": """
            QWidget {
                background-color: #f9f9f9;
                color: #333;
                font-family: "Georgia", serif;
            }
            QTreeWidgetItem[is-category="true"] {
            background-color: #f7f7f5;
            font-weight: bold;
            }

            QLineEdit, QTextEdit {
                background-color: #ffffff;
                color: #000;
                border: 1px solid #ccc;
            }
            QPushButton {
                background-color: #f1f1f1;
                color: #333;
                border: 2px solid #333;
                padding: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e1e1e1;
            }
            QTreeView, QTreeWidget {
                background-color: #f9f9f9;
                color: #333;
            }
            QHeaderView::section {
                background-color: #e1e1e1;
                color: #333;
                padding: 4px;
            }
            QTabBar::tab {
                background: #f1f1f1;
                color: #333;
                padding: 5px;
            }
            QTabBar::tab:selected {
                background: #ddd;
            }
        """,
        "Ocean Breeze": """
            QWidget {
                background-color: #e0f7fa;
                color: #0277bd;
                font-family: "Verdana", sans-serif;
            }
            QTreeWidgetItem[is-category="true"] {
            background-color: #d6f5f9;
            font-weight: bold;
            } 
            QLineEdit, QTextEdit {
                background-color: #b2ebf2;
                color: #004d40;
                border: 1px solid #0288d1;
            }
            QPushButton {
                background-color: #4dd0e1;
                color: #004d40;
                border: 2px solid #004d40;
                padding: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #26c6da;
            }
            QTreeView, QTreeWidget {
                background-color: #b2ebf2;
                color: #004d40;
            }
            QHeaderView::section {
                background-color: #4dd0e1;
                color: #004d40;
                padding: 4px;
            }
            QTabBar::tab {
                background: #b2ebf2;
                color: #0277bd;
                padding: 5px;
            }
            QTabBar::tab:selected {
                background: #4dd0e1;
            }
        """,
        "Sepia": """
            QWidget {
                background-color: #f4ecd8;
                color: #5a4630;
                font-family: "Times New Roman", serif;
            }
            QTreeWidgetItem[is-category="true"] {
            background-color: #f9f2e5;
            font-weight: bold;
        }
            QLineEdit, QTextEdit {
                background-color: #f8f1e4;
                color: #3a2c1f;
                border: 1px solid #a67c52;
            }
            QPushButton {
                background-color: #d8c3a5;
                color: #3a2c1f;
                border: 2px solid #3a2c1f;
                padding: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c4a484;
            }
            QTreeView, QTreeWidget {
                background-color: #f4ecd8;
                color: #5a4630;
            }
            QHeaderView::section {
                background-color: #d8c3a5;
                color: #5a4630;
                padding: 4px;
            }
            QTabBar::tab {
                background: #d8c3a5;
                color: #5a4630;
                padding: 5px;
            }
            QTabBar::tab:selected {
                background: #c4a484;
            }
        """,
        
        "Notion Light": """
            /* Enhanced Notion Light Theme with Accessibility Features */
            QWidget {
                background-color: #ffffff;
                color: #37352f;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                font-size: 14px;
                line-height: 1.5;
            }
            QTreeWidgetItem[is-category="true"] {
            background-color: #f7f7f5;
            font-weight: bold;
            }

            /* Main window styling */
            QMainWindow {
                background-color: #ffffff;
            }

            /* Text editing areas */
            QTextEdit, QPlainTextEdit {
                background-color: #ffffff;
                color: #37352f;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 12px;
                font-family: "SF Pro Text", -apple-system, BlinkMacSystemFont, sans-serif;
                font-size: 15px;
                line-height: 1.6;
                selection-background-color: #e7f5ff;
                selection-color: #0066cc;
            }

            QTextEdit:focus {
                border: 2px solid #0066cc;
                outline: none;
            }

            /* Input fields */
            QLineEdit {
                background-color: #f7f7f5;
                color: #37352f;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
            }

            QLineEdit:focus {
                border: 2px solid #0066cc;
                background-color: #ffffff;
                outline: none;
            }

            /* Buttons */
            QPushButton {
                background-color: #f7f7f5;
                color: #37352f;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 500;
                widget-animation-duration: 200;
            }

            QPushButton:hover {
                background-color: #efefef;
                border-color: #d0d0d0;
            }

            QPushButton:pressed {
                background-color: #e0e0e0;
            }

            QPushButton[primary="true"] {
                background-color: #0066cc;
                color: white;
                border: none;
            }

            QPushButton[primary="true"]:hover {
                background-color: #0052a3;
            }

            /* Tree views */
            QTreeView, QTreeWidget {
                background-color: #ffffff;
                color: #37352f;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                alternate-background-color: #f7f7f5;
                outline: 0;
            }

            QTreeView::item, QTreeWidget::item {
                padding: 8px;
                border-radius: 4px;
            }

            QTreeView::item:hover, QTreeWidget::item:hover {
                background-color: #f0f0f0;
            }

            QTreeView::item:selected, QTreeWidget::item:selected {
                background-color: #e7f5ff;
                color: #0066cc;
            }

            /* Headers */
            QHeaderView::section {
                background-color: #f7f7f5;
                color: #37352f;
                padding: 12px 8px;
                border: none;
                border-bottom: 1px solid #e0e0e0;
                font-weight: 600;
                font-size: 13px;
            }

            /* Tabs */
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: #ffffff;
            }

            QTabBar::tab {
                background-color: #f7f7f5;
                color: #6b6b6b;
                padding: 12px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 14px;
                font-weight: 500;
            }

            QTabBar::tab:hover {
                background-color: #efefef;
                color: #37352f;
            }

            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #37352f;
                border: 1px solid #e0e0e0;
                border-bottom: 2px solid #0066cc;
            }

            /* Toolbars */
            QToolBar {
                background-color: #ffffff;
                border: none;
                border-bottom: 1px solid #e0e0e0;
                padding: 8px;
                spacing: 8px;
            }

            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
            }

            QToolButton:hover {
                background-color: #f0f0f0;
            }

            QToolButton:pressed {
                background-color: #e0e0e0;
            }

            /* Scrollbars */
            QScrollBar:vertical {
                background-color: #f7f7f5;
                width: 12px;
                border-radius: 6px;
            }

            QScrollBar::handle:vertical {
                background-color: #d0d0d0;
                border-radius: 6px;
                min-height: 20px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: #b0b0b0;
            }

            QScrollBar:horizontal {
                background-color: #f7f7f5;
                height: 12px;
                border-radius: 6px;
            }

            QScrollBar::handle:horizontal {
                background-color: #d0d0d0;
                border-radius: 6px;
                min-width: 20px;
            }

            QScrollBar::handle:horizontal:hover {
                background-color: #b0b0b0;
            }

            /* Menus */
            QMenuBar {
                background-color: #ffffff;
                border-bottom: 1px solid #e0e0e0;
                padding: 4px;
            }

            QMenuBar::item {
                background-color: transparent;
                padding: 8px 12px;
                border-radius: 4px;
            }

            QMenuBar::item:selected {
                background-color: #f0f0f0;
            }

            QMenu {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 4px;
            }

            QMenu::item {
                padding: 8px 16px;
                border-radius: 4px;
            }

            QMenu::item:selected {
                background-color: #e7f5ff;
                color: #0066cc;
            }
        """,
        
            "Warm Cream": """
            /* Warm Cream — soft paper & sepia ink */
            QWidget {
                background-color: #fdfcfa;
                color: #5a4d41;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                font-size: 14px;
                line-height: 1.5;
            }
            QTreeWidgetItem[is-category="true"] {
            background-color: #f5e8d0;
            font-weight: bold;
            }

            /* Main window styling */
            QMainWindow {
                background-color: #fdfcfa;
            }

            /* Text editing areas */
            QTextEdit, QPlainTextEdit {
                background-color: #fdfcfa;
                color: #5a4d41;
                border: 1px solid #e8e0d8;
                border-radius: 8px;
                padding: 12px;
                font-family: "SF Pro Text", -apple-system, BlinkMacSystemFont, sans-serif;
                font-size: 15px;
                line-height: 1.6;
                selection-background-color: #f5e8d0;
                selection-color: #8b5e3c;
            }

            QTextEdit:focus {
                border: 2px solid #c9996b;
                outline: none;
            }

            /* Input fields */
            QLineEdit {
                background-color: #f7f3ef;
                color: #5a4d41;
                border: 1px solid #e8e0d8;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
            }

            QLineEdit:focus {
                border: 2px solid #c9996b;
                background-color: #fdfcfa;
                outline: none;
            }

            /* Buttons */
            QPushButton {
                background-color: #f7f3ef;
                color: #5a4d41;
                border: 1px solid #e8e0d8;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 500;
                widget-animation-duration: 200;
            }

            QPushButton:hover {
                background-color: #ede4da;
                border-color: #d6c7b8;
            }

            QPushButton:pressed {
                background-color: #e8d0b8;
            }

            QPushButton[primary="true"] {
                background-color: #c9996b;
                color: white;
                border: none;
            }

            QPushButton[primary="true"]:hover {
                background-color: #b8885c;
            }

            /* Tree views */
            QTreeView, QTreeWidget {
                background-color: #fdfcfa;
                color: #5a4d41;
                border: 1px solid #e8e0d8;
                border-radius: 8px;
                alternate-background-color: #f7f3ef;
                outline: 0;
            }

            QTreeView::item, QTreeWidget::item {
                padding: 8px;
                border-radius: 4px;
            }

            QTreeView::item:hover, QTreeWidget::item:hover {
                background-color: #f0e8dd;
            }

            QTreeView::item:selected, QTreeWidget::item:selected {
                background-color: #e8d0b8;
                color: #8b5e3c;
            }

            /* Headers */
            QHeaderView::section {
                background-color: #f7f3ef;
                color: #5a4d41;
                padding: 12px 8px;
                border: none;
                border-bottom: 1px solid #e8e0d8;
                font-weight: 600;
                font-size: 13px;
            }

            /* Tabs */
            QTabWidget::pane {
                border: 1px solid #e8e0d8;
                border-radius: 8px;
                background-color: #fdfcfa;
            }

            QTabBar::tab {
                background-color: #f7f3ef;
                color: #8b8b8b;
                padding: 12px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 14px;
                font-weight: 500;
            }

            QTabBar::tab:hover {
                background-color: #ede4da;
                color: #5a4d41;
            }

            QTabBar::tab:selected {
                background-color: #fdfcfa;
                color: #5a4d41;
                border: 1px solid #e8e0d8;
                border-bottom: 2px solid #c9996b;
            }

            /* Toolbars */
            QToolBar {
                background-color: #fdfcfa;
                border: none;
                border-bottom: 1px solid #e8e0d8;
                padding: 8px;
                spacing: 8px;
            }

            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
            }

            QToolButton:hover {
                background-color: #f0e8dd;
            }

            QToolButton:pressed {
                background-color: #e8d0b8;
            }

            /* Scrollbars */
            QScrollBar:vertical {
                background-color: #f7f3ef;
                width: 12px;
                border-radius: 6px;
            }

            QScrollBar::handle:vertical {
                background-color: #d6c7b8;
                border-radius: 6px;
                min-height: 20px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: #c9b8a8;
            }

            QScrollBar:horizontal {
                background-color: #f7f3ef;
                height: 12px;
                border-radius: 6px;
            }

            QScrollBar::handle:horizontal {
                background-color: #d6c7b8;
                border-radius: 6px;
                min-width: 20px;
            }

            QScrollBar::handle:horizontal:hover {
                background-color: #c9b8a8;
            }

            /* Menus */
            QMenuBar {
                background-color: #fdfcfa;
                border-bottom: 1px solid #e8e0d8;
                padding: 4px;
            }

            QMenuBar::item {
                background-color: transparent;
                padding: 8px 12px;
                border-radius: 4px;
            }

            QMenuBar::item:selected {
                background-color: #f0e8dd;
            }

            QMenu {
                background-color: #fdfcfa;
                border: 1px solid #e8e0d8;
                border-radius: 8px;
                padding: 4px;
            }

            QMenu::item {
                padding: 8px 16px;
                border-radius: 4px;
            }

            QMenu::item:selected {
                background-color: #e8d0b8;
                color: #8b5e3c;
            }
        """,
    }

    ICON_TINTS = {
    # Light themes → dark icons
    "Standard":      "#333333",
    "Paper White":   "#333333",
    "Ocean Breeze":  "#004d40",
    "Sepia":         "#3a2c1f",
    "Notion Light":  "#37352f",
    "Warm Cream":    "#4a4239",

    # Dark themes → light icons
    "Night Mode":    "#ffffff",
    "Solarized Dark":"#fdf6e3",
    }

    _current_theme = "default"

    @classmethod
    def list_themes(cls):
        return list(cls.THEMES.keys())

    @classmethod
    def get_stylesheet(cls, theme_name):
        return cls.THEMES.get(theme_name, cls.THEMES["Notion Light"])

    @classmethod
    def apply_theme(cls, widget, theme_name):
        stylesheet = cls.get_stylesheet(theme_name)
        widget.setStyleSheet(stylesheet)
        cls.clear_icon_cache()

    @classmethod
    def apply_to_app(cls, theme_name):
        if theme_name in cls.THEMES:
            cls._current_theme = theme_name

        stylesheet = cls.get_stylesheet(theme_name)
        app = QApplication.instance()
        if app and hasattr(app, 'setStyleSheet'):
            app.setStyleSheet(stylesheet)
            cls.clear_icon_cache()
            # Emit theme change signal from the instance
            if cls._instance:
                cls._instance.themeChanged.emit(theme_name)
        else:
            raise RuntimeError(
                "No QApplication instance found. Create one before applying a theme.")


    @staticmethod
    def get_tinted_icon(file_path, tint_color=None, theme_name=None, size=None):
        theme = theme_name or ThemeManager._current_theme
        if tint_color is None:
            tint_color = ThemeManager.ICON_TINTS.get(theme)
        cache_key = (file_path, str(tint_color) if isinstance(tint_color, QColor) else tint_color)

        if cache_key in ThemeManager._icon_cache:
            return ThemeManager._icon_cache[cache_key]

        renderer = QSvgRenderer(file_path)
        if not renderer.isValid():
            return QIcon()

        default_size = renderer.defaultSize()
        if size is None:
            size = default_size
        else:
            size = size if hasattr(size, 'width') else QSize(size, size)

        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        if tint_color:
            if isinstance(tint_color, str):
                tint_color = QColor(tint_color)
            elif not isinstance(tint_color, QColor):
                tint_color = QColor("white")

            tinted_pixmap = QPixmap(size)
            tinted_pixmap.fill(Qt.GlobalColor.transparent)

            painter = QPainter(tinted_pixmap)
            painter.drawPixmap(0, 0, pixmap)
            painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)
            painter.fillRect(pixmap.rect(), tint_color)
            painter.end()

            pixmap = tinted_pixmap

        icon = QIcon(pixmap)
        ThemeManager._icon_cache[cache_key] = icon
        return icon
    
    @classmethod
    def calculate_contrast_ratio(cls, color1, color2):
        """Calculate the contrast ratio between two QColor objects."""
        def luminance(color):
            r, g, b = color.redF(), color.greenF(), color.blueF()
            return 0.2126 * r + 0.7152 * g + 0.0722 * b
        l1 = luminance(color1) + 0.05
        l2 = luminance(color2) + 0.05
        return max(l1, l2) / min(l1, l2)

    @classmethod
    def get_category_background_color(cls):
        """
        Return a color for category row background based on the current theme.
        """
        settings = WWSettingsManager.get_appearance_settings()
        if not settings.get("enable_category_background", True):
            return QColor(Qt.GlobalColor.transparent)

        theme = cls._current_theme
        colors = {
            "Standard": QColor("#e0e0e0"),  # Light grey
            "Night Mode": QColor("#424242"),  # Charcoal
            "Solarized Dark": QColor("#073642"),  # Deep teal
            "Paper White": QColor("#f5f5f5"),  # Light grey
            "Ocean Breeze": QColor("#d6f5f9"),  # Light blue
            "Sepia": QColor("#f9f2e5"),  # Sepia tone
            "Notion Light": QColor("#f7f7f5"),  # Light grey
            "Warm Cream": QColor("#f5e8d0"),  # Cream tone
        }
        return colors.get(theme, QColor("#f7f7f5"))  # Default to light grey

    @classmethod
    def get_theme_palette(cls, theme_name):
        """Get the color palette for a specific theme."""
        palettes = {
            "Standard": {
                "background": "#e0e0e0",
                "text": "black",
                "accent": "#0078d4",
                "border": "#cccccc",
                "hover": "#d0d0d0"
            },
            "Paper White": {
                "background": "#f9f9f9",
                "text": "#333333",
                "accent": "#333333",
                "border": "#cccccc",
                "hover": "#e1e1e1"
            },
            "Ocean Breeze": {
                "background": "#e0f7fa",
                "text": "#0277bd",
                "accent": "#4dd0e1",
                "border": "#0288d1",
                "hover": "#b2ebf2"
            },
            "Sepia": {
                "background": "#f4ecd8",
                "text": "#5a4630",
                "accent": "#d8c3a5",
                "border": "#a67c52",
                "hover": "#c4a484"
            },
            "Night Mode": {
                "background": "#2b2b2b",
                "text": "#ffffff",
                "accent": "#ffffff",
                "border": "#555555",
                "hover": "#444444"
            },
            "Solarized Dark": {
                "background": "#002b36",
                "text": "#839496",
                "accent": "#586e75",
                "border": "#586e75",
                "hover": "#073642"
            },
            "Notion Light": {
                "background": "#ffffff",
                "text": "#37352f",
                "accent": "#0066cc",
                "border": "#e0e0e0",
                "hover": "#f0f0f0"
            },
            "Warm Cream": {
                "background": "#fdfcfa",
                "text": "#4a4239",
                "accent": "#c9996b",
                "border": "#e8e0d8",
                "hover": "#f5e8d6"
            },
        }
        return palettes.get(theme_name, palettes["default"])

    @classmethod
    def clear_icon_cache(cls):
        """Clear the icon cache to force re-tinting with new theme colors."""
        cls._icon_cache.clear()

    @classmethod
    def refresh_all_icons(cls):
        """Refresh all icons in the application with current theme colors."""
        cls.clear_icon_cache()
        app = QApplication.instance()
        if app and isinstance(app, QApplication):
            # Force a repaint of all widgets
            for widget in app.allWidgets():
                widget.update()



if __name__ == '__main__':
    print("Available themes:")
    for theme in ThemeManager.list_themes():
        print(f" - {theme}")
