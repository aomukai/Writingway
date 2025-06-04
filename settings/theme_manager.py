from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon, QColor, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer
from .settings_manager import WWSettingsManager

class ThemeManager:
    """
    A simple manager for predefined themes.

    Provides methods to:
      - List available themes.
      - Retrieve a stylesheet for a given theme.
      - Apply a theme to a specific widget or the entire application.
      - Generate tinted SVG icons using QSvgRenderer.
    """
    _icon_cache = {}  # Cache: (file_path, tint_color) -> QIcon

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
            QTreeWidgetItem[is-category="true"] {
                background-color: #4a4d4f; /* Fallback for Night Mode */
                font-weight: bold;
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
            QTreeWidgetItem[is-category="true"] {
                background-color: #0a4b5a; /* Fallback for Solarized Dark */
                font-weight: bold;
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
            QTreeWidgetItem[is-category="true"] {
                background-color: #f0f0f0; /* Fallback for Paper White */
                font-weight: bold;
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
            QTreeWidgetItem[is-category="true"] {
                background-color: #c8f3f8; /* Fallback for Ocean Breeze */
                font-weight: bold;
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
            QTreeWidgetItem[is-category="true"] {
                background-color: #f8f1e4; /* Fallback for Sepia */
                font-weight: bold;
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
        """
    }

    ICON_TINTS = {
        "Standard": "black",
        "Paper White": "black",
        "Ocean Breeze": "black",
        "Sepia": "black",
        "Night Mode": "white",
        "Solarized Dark": "#fdf6e3",
    }

    _current_theme = "Default"  # Track current theme

    @classmethod
    def list_themes(cls):
        """
        Return a list of available theme names.
        """
        return list(cls.THEMES.keys())

    @classmethod
    def get_stylesheet(cls, theme_name):
        """
        Retrieve the stylesheet string for a given theme name.
        """
        return cls.THEMES.get(theme_name, "")

    @classmethod
    def apply_theme(cls, widget, theme_name):
        """
        Apply the stylesheet of the specified theme to the given widget.
        """
        stylesheet = cls.get_stylesheet(theme_name)
        widget.setStyleSheet(stylesheet)

    @classmethod
    def apply_to_app(cls, theme_name):
        """
        Apply the theme to the entire application.
        """
        if theme_name in cls.THEMES:
            cls._current_theme = theme_name

        stylesheet = cls.get_stylesheet(theme_name)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(stylesheet)
        else:
            raise RuntimeError(
                "No QApplication instance found. Create one before applying a theme.")

    @staticmethod
    def get_tinted_icon(file_path, tint_color=None, theme_name=None, size=None):
        """
        Generate a tinted QIcon from a file path.
        
        Args:
            file_path (str): Path to the icon file (e.g., SVG, PNG).
            tint_color (str or QColor, optional): Color to tint the icon (e.g., 'white', '#ffffff', QColor).
            theme_name (str, optional): Theme to use for default tint color. Defaults to current theme.
        
        Returns:
            QIcon: Tinted SVG icon, or original icon if tint_color is None.
        """
        # Normalize tint_color for cache key
        theme = theme_name or ThemeManager._current_theme
        if tint_color is None:
            tint_color = ThemeManager.ICON_TINTS.get(theme)
        cache_key = (file_path, str(tint_color) if isinstance(tint_color, QColor) else tint_color)
        
        if cache_key in ThemeManager._icon_cache:
            return ThemeManager._icon_cache[cache_key]
        
        # Load SVG renderer
        renderer = QSvgRenderer(file_path)
        if not renderer.isValid():
            return QIcon()  # Return empty icon if SVG loading fails
        
        # Use default size from SVG or provided size
        default_size = renderer.defaultSize()
        if size is None:
            size = default_size
        else:
            size = size if hasattr(size, 'width') else QSize(size, size)
        
        # Create pixmap for rendering
        pixmap = QPixmap(size)
        pixmap.fill(Qt.transparent)
        
        # Render SVG to pixmap
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        
        # Apply tint if needed
        if tint_color:
            # Convert tint_color to QColor
            if isinstance(tint_color, str):
                tint_color = QColor(tint_color)
            elif not isinstance(tint_color, QColor):
                tint_color = QColor("white")  # Fallback
            
            # Create a tinted pixmap
            tinted_pixmap = QPixmap(size)
            tinted_pixmap.fill(Qt.transparent)
            
            painter = QPainter(tinted_pixmap)
            # Draw original pixmap
            painter.drawPixmap(0, 0, pixmap)
            # Apply tint overlay with SourceAtop composition mode
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
        """Get a theme-appropriate background color for category rows in QTreeWidget."""
        if not WWSettingsManager.get_appearance_settings().get("enable_category_background", True):
            return QColor(Qt.transparent)  # No category background if disabled
        theme_name = cls._current_theme
        stylesheet = cls.get_stylesheet(theme_name)
        # Default fallback color
        default_color = QColor("#e0e0e0")  # Light gray for contrast with black text
        bg_color = default_color

        # Parse QTreeWidget background color from stylesheet
        if stylesheet:
            lines = stylesheet.splitlines()
            in_tree_widget_block = False
            for line in lines:
                line = line.strip()
                if "QTreeWidget {" in line:
                    in_tree_widget_block = True
                    continue
                if in_tree_widget_block:
                    if "}" in line:
                        in_tree_widget_block = False
                        break
                    if "background-color" in line:
                        color_str = line.split("background-color:")[-1].split(";")[0].strip()
                        if QColor(color_str).isValid():
                            bg_color = QColor(color_str)
                            break

        # Adjust lightness to differentiate category rows
        h, s, l, a = bg_color.getHslF()
        # Target lightness > 0.8 for contrast with black text
        new_lightness = min(1.0, max(0.8, l - 0.05))  # Slightly lighter for distinction
        adjusted_color = QColor.fromHslF(h, s, new_lightness, a)

        # Verify contrast ratio with black text (#000000)
        black = QColor("black")
        contrast_ratio = cls.calculate_contrast_ratio(adjusted_color, black)
        if contrast_ratio < 4.5:
            # If contrast is too low, use a lighter gray
            adjusted_color = QColor("#f0f0f0")  # Very light gray

        return adjusted_color


if __name__ == '__main__':
    print("Available themes:")
    for theme in ThemeManager.list_themes():
        print(f" - {theme}")
