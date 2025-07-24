from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QApplication, QProxyStyle, QStyle
from PyQt5.QtGui import QIcon, QColor, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer
from .settings_manager import WWSettingsManager


class ThemeManager:
    """
    theme manager for Writingway with contemporary design patterns.

    Provides:
    - CSS styling with glassmorphism and neumorphism effects
    - Beautiful themes inspired by Notion, Obsidian, and contemporary writing apps
    - Smooth animations and hover effects
    - Dark/light mode switching
    - typography and spacing
    """
    _icon_cache = {}  # Cache: (file_path, tint_color) -> QIcon

    # CSS themes with glassmorphism and neumorphism effects
    THEMES = {
        "Notion Light": """
            /* Enhanced Notion Light Theme with Accessibility Features */
            QWidget {
                background-color: #ffffff;
                color: #37352f;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                font-size: 14px;
                line-height: 1.5;
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

            QTreeWidgetItem[is-category="true"] {
                background-color: #f7f7f5;
                font-weight: 600;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: 12px 8px;
                border-bottom: 1px solid #e0e0e0;
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

            QTreeWidgetItem[is-category="true"] {
                background-color: #f7f3ef;
                font-weight: 600;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: 12px 8px;
                border-bottom: 1px solid #e8e0d8;
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
                
            "Warm Ivory": """
            /* Warm Ivory — soft paper & soft sand */
            QWidget {
                background-color: #fffdf9;
                color: #5a4d41;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                font-size: 14px;
                line-height: 1.5;
            }

            /* Main window styling */
            QMainWindow {
                background-color: #fffdf9;
            }

            /* Text editing areas */
            QTextEdit, QPlainTextEdit {
                background-color: #fffdf9;
                color: #5a4d41;
                border: 1px solid #e6dfd4;
                border-radius: 8px;
                padding: 12px;
                font-family: "SF Pro Text", -apple-system, BlinkMacSystemFont, sans-serif;
                font-size: 15px;
                line-height: 1.6;
                selection-background-color: #f5e8d0;
                selection-color: #8b5e3c;
            }

            QTextEdit:focus {
                border: 2px solid #d4a76a;
                outline: none;
            }

            /* Input fields */
            QLineEdit {
                background-color: #f8f4ef;
                color: #5a4d41;
                border: 1px solid #e6dfd4;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
            }

            QLineEdit:focus {
                border: 2px solid #d4a76a;
                background-color: #fffdf9;
                outline: none;
            }

            /* Buttons */
            QPushButton {
                background-color: #f8f4ef;
                color: #5a4d41;
                border: 1px solid #e6dfd4;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 500;
                widget-animation-duration: 200;
            }

            QPushButton:hover {
                background-color: #f0e8dd;
                border-color: #d6c7b8;
            }

            QPushButton:pressed {
                background-color: #e6dfd4;
            }

            QPushButton[primary="true"] {
                background-color: #d4a76a;
                color: white;
                border: none;
            }

            QPushButton[primary="true"]:hover {
                background-color: #c4965a;
            }

            /* Tree views */
            QTreeView, QTreeWidget {
                background-color: #fffdf9;
                color: #5a4d41;
                border: 1px solid #e6dfd4;
                border-radius: 8px;
                alternate-background-color: #f8f4ef;
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
                background-color: #e8d9c0;
                color: #8b5e3c;
            }

            QTreeWidgetItem[is-category="true"] {
                background-color: #f8f4ef;
                font-weight: 600;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: 12px 8px;
                border-bottom: 1px solid #e6dfd4;
            }

            /* Headers */
            QHeaderView::section {
                background-color: #f8f4ef;
                color: #5a4d41;
                padding: 12px 8px;
                border: none;
                border-bottom: 1px solid #e6dfd4;
                font-weight: 600;
                font-size: 13px;
            }

            /* Tabs */
            QTabWidget::pane {
                border: 1px solid #e6dfd4;
                border-radius: 8px;
                background-color: #fffdf9;
            }

            QTabBar::tab {
                background-color: #f8f4ef;
                color: #8b8b8b;
                padding: 12px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 14px;
                font-weight: 500;
            }

            QTabBar::tab:hover {
                background-color: #f0e8dd;
                color: #5a4d41;
            }

            QTabBar::tab:selected {
                background-color: #fffdf9;
                color: #5a4d41;
                border: 1px solid #e6dfd4;
                border-bottom: 2px solid #d4a76a;
            }

            /* Toolbars */
            QToolBar {
                background-color: #fffdf9;
                border: none;
                border-bottom: 1px solid #e6dfd4;
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
                background-color: #e8d9c0;
            }

            /* Scrollbars */
            QScrollBar:vertical {
                background-color: #f8f4ef;
                width: 12px;
                border-radius: 6px;
            }

            QScrollBar::handle:vertical {
                background-color: #d4c0a8;
                border-radius: 6px;
                min-height: 20px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: #c0a58a;
            }

            QScrollBar:horizontal {
                background-color: #f8f4ef;
                height: 12px;
                border-radius: 6px;
            }

            QScrollBar::handle:horizontal {
                background-color: #d4c0a8;
                border-radius: 6px;
                min-width: 20px;
            }

            QScrollBar::handle:horizontal:hover {
                background-color: #c0a58a;
            }

            /* Menus */
            QMenuBar {
                background-color: #fffdf9;
                border-bottom: 1px solid #e6dfd4;
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
                background-color: #fffdf9;
                border: 1px solid #e6dfd4;
                border-radius: 8px;
                padding: 4px;
            }

            QMenu::item {
                padding: 8px 16px;
                border-radius: 4px;
            }

            QMenu::item:selected {
                background-color: #e8d9c0;
                color: #8b5e3c;
            }
        """,
    
        "Warm Blush": """
    /* Warm Blush — rosy parchment & soft terracotta */
    QWidget {
        background-color: #fff8f6;
        color: #654a4a;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        font-size: 14px;
        line-height: 1.5;
    }

    QMainWindow {
        background-color: #fff8f6;
    }

    QTextEdit, QPlainTextEdit {
        background-color: #fff8f6;
        color: #654a4a;
        border: 1px solid #f3ddd9;
        border-radius: 8px;
        padding: 12px;
        font-family: "SF Pro Text", -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 15px;
        line-height: 1.6;
        selection-background-color: #ffe9e0;
        selection-color: #b95c4a;
    }

    QTextEdit:focus {
        border: 2px solid #e79b83;
        outline: none;
    }

    QLineEdit {
        background-color: #fdf2f0;
        color: #654a4a;
        border: 1px solid #f3ddd9;
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 14px;
    }

    QLineEdit:focus {
        border: 2px solid #e79b83;
        background-color: #fff8f6;
        outline: none;
    }

    QPushButton {
        background-color: #fdf2f0;
        color: #654a4a;
        border: 1px solid #f3ddd9;
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 14px;
        font-weight: 500;
        transition: all 0.2s ease;
    }

    QPushButton:hover {
        background-color: #fae8e4;
        border-color: #f3ddd9;
    }

    QPushButton:pressed {
        background-color: #f3ddd9;
    }

    QPushButton[primary="true"] {
        background-color: #e79b83;
        color: white;
        border: none;
    }

    QPushButton[primary="true"]:hover {
        background-color: #d88a73;
    }

    /* Tree views */
    QTreeView, QTreeWidget {
        background-color: #fff8f6;
        color: #654a4a;
        border: 1px solid #f3ddd9;
        border-radius: 8px;
        alternate-background-color: #fdf2f0;
        outline: 0;
    }

    QTreeView::item, QTreeWidget::item {
        padding: 8px;
        border-radius: 4px;
    }

    QTreeView::item:hover, QTreeWidget::item:hover {
        background-color: #fae8e4;
    }

    QTreeView::item:selected, QTreeWidget::item:selected {
        background-color: #ffd1c4;
        color: #b95c4a;
    }

    QTreeWidgetItem[is-category="true"] {
        background-color: #fdf2f0;
        font-weight: 600;
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 12px 8px;
        border-bottom: 1px solid #f3ddd9;
    }

    /* Headers */
    QHeaderView::section {
        background-color: #fdf2f0;
        color: #654a4a;
        padding: 12px 8px;
        border: none;
        border-bottom: 1px solid #f3ddd9;
        font-weight: 600;
        font-size: 13px;
    }

    /* Tabs */
    QTabWidget::pane {
        border: 1px solid #f3ddd9;
        border-radius: 8px;
        background-color: #fff8f6;
    }

    QTabBar::tab {
        background-color: #fdf2f0;
        color: #8b8b8b;
        padding: 12px 20px;
        margin-right: 2px;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        font-size: 14px;
        font-weight: 500;
    }

    QTabBar::tab:hover {
        background-color: #fae8e4;
        color: #654a4a;
    }

    QTabBar::tab:selected {
        background-color: #fff8f6;
        color: #654a4a;
        border: 1px solid #f3ddd9;
        border-bottom: 2px solid #e79b83;
    }

    /* Toolbars */
    QToolBar {
        background-color: #fff8f6;
        border: none;
        border-bottom: 1px solid #f3ddd9;
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
        background-color: #fae8e4;
    }

    QToolButton:pressed {
        background-color: #ffd1c4;
    }

    /* Scrollbars */
    QScrollBar:vertical {
        background-color: #fdf2f0;
        width: 12px;
        border-radius: 6px;
    }

    QScrollBar::handle:vertical {
        background-color: #e7b5a8;
        border-radius: 6px;
        min-height: 20px;
    }

    QScrollBar::handle:vertical:hover {
        background-color: #d49d8f;
    }

    QScrollBar:horizontal {
        background-color: #fdf2f0;
        height: 12px;
        border-radius: 6px;
    }

    QScrollBar::handle:horizontal {
        background-color: #e7b5a8;
        border-radius: 6px;
        min-width: 20px;
    }

    QScrollBar::handle:horizontal:hover {
        background-color: #d49d8f;
    }

    /* Menus */
    QMenuBar {
        background-color: #fff8f6;
        border-bottom: 1px solid #f3ddd9;
        padding: 4px;
    }

    QMenuBar::item {
        background-color: transparent;
        padding: 8px 12px;
        border-radius: 4px;
    }

    QMenuBar::item:selected {
        background-color: #fae8e4;
    }

    QMenu {
        background-color: #fff8f6;
        border: 1px solid #f3ddd9;
        border-radius: 8px;
        padding: 4px;
    }

    QMenu::item {
        padding: 8px 16px;
        border-radius: 4px;
    }

    QMenu::item:selected {
        background-color: #ffd1c4;
        color: #b95c4a;
    }
"""
    }

    ICON_TINTS = {
        "Notion Light": "#37352f",
        "Glassmorphism Light": "#2c3e50",
        "Glassmorphism Dark": "#e0e0e0",
        "Minimal Light": "#1a1a1a",
        "Minimal Dark": "#e6e6e6",
        "Warm Cream":   "#4a4239",
        "Warm Ivory":  "#5a4d41",
        "Warm Blush":  "#654a4a",
    }

    _current_theme = "Notion Light"

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
        if app:
            app.setStyleSheet(stylesheet)
            cls.clear_icon_cache()
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
        """Get a theme-appropriate background color for category rows."""
        if not WWSettingsManager.get_appearance_settings().get("enable_category_background", True):
            return QColor(Qt.GlobalColor.transparent)
            
        theme_name = cls._current_theme
        stylesheet = cls.get_stylesheet(theme_name)
        
        # Default colors based on theme type
        if "Light" in theme_name or "light" in theme_name.lower():
            default_color = QColor("#f7f7f5")
        else:
            default_color = QColor("#2d2d2d")
            
        return default_color

    @classmethod
    def get_theme_palette(cls, theme_name):
        """Get the color palette for a specific theme."""
        palettes = {
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
            "Warm Ivory": {
            "background": "#fffdf9",
            "text": "#5a4d41",
            "accent": "#d4a76a",
            "border": "#e6dfd4",
            "hover": "#f0e8dd"
            },
            "Warm Blush": {
            "background": "#fff8f6",
            "text": "#654a4a",
            "accent": "#e79b83",
            "border": "#f3ddd9",
            "hover": "#fae8e4"
            },
        }
        return palettes.get(theme_name, palettes["Notion Light"])

    @classmethod
    def clear_icon_cache(cls):
        """Clear the icon cache to force re-tinting with new theme colors."""
        cls._icon_cache.clear()

    @classmethod
    def refresh_all_icons(cls):
        """Refresh all icons in the application with current theme colors."""
        cls.clear_icon_cache()
        app = QApplication.instance()
        app = QApplication.instance()
        if app and isinstance(app, QApplication):
            # Force a repaint of all widgets
            for widget in app.allWidgets():
                widget.update()



if __name__ == '__main__':
    print("Available themes:")
    for theme in ThemeManager.list_themes():
        print(f" - {theme}")
