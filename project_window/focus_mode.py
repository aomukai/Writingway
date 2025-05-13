#!/usr/bin/env python3
import os
import sys
import re
from PyQt5.QtCore import Qt, QPropertyAnimation
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QGridLayout, QVBoxLayout,
    QGraphicsOpacityEffect, QApplication, QTextEdit
)
from PyQt5.QtGui import QPixmap, QKeyEvent

# Subclass QTextEdit to force plain text paste


class PlainTextEdit(QTextEdit):
    def __init__(self):
        super().__init__()
        self.zoom_factor = 10  # Default zoom level
       
    def adjust_zoom(self, delta):
        # Update zoom factor (ensure it stays within reasonable bounds)
        self.zoom_factor = max(5, min(self.zoom_factor + delta, 30))  # 50% to 300%
        
        # Apply the zoom factor to the viewport
        stylesheet = self.styleSheet();
        loc = stylesheet.find("font-size")
        if loc == -1:
            stylesheet += f" font-size: {self.zoom_factor * 10}%;"
        else:
            stylesheet = re.sub(r"font-size: \d+%;", f"font-size: {self.zoom_factor * 10}%;", stylesheet)
        self.setStyleSheet(stylesheet)
        self.viewport().set
        self.viewport().update()  # Refresh the display

    def toHtmlPreservingOriginal(self):
        # Export the HTML without the zoom factor affecting font sizes
        return self.document().toHtml()
    
    def insertFromMimeData(self, source):
        self.insertPlainText(source.text())


class FocusMode(QMainWindow):
    def __init__(self, image_dir, scene_text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Focus Mode"))
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.showFullScreen()
        # NEW: Callback attribute to be set by the parent window
        self.on_close = None

        # Prepare image list: load all PNG files, sorted alphabetically.
        self.image_dir = image_dir
        self.image_files = sorted(
            [f for f in os.listdir(image_dir) if f.lower().endswith('.png')]
        )
        self.current_index = 0

        # Keep a reference to the animation to prevent garbage collection.
        self.animation = None

        # Central widget with grid layout to layer background and foreground.
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QGridLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Background label to display the image (fills the entire window)
        self.bg_label = QLabel(central_widget)
        self.bg_label.setAlignment(Qt.AlignCenter)
        self.bg_label.setScaledContents(True)
        layout.addWidget(self.bg_label, 0, 0)

        # Foreground widget: container for the "A4 page"
        self.fg_widget = QWidget(central_widget)
        self.fg_widget.setAttribute(Qt.WA_TranslucentBackground)
        fg_layout = QVBoxLayout(self.fg_widget)
        fg_layout.setContentsMargins(0, 0, 0, 0)
        fg_layout.setSpacing(0)
        fg_layout.addStretch()

        # Create a centered A4 page widget (fixed size to simulate A4)
        self.page_widget = QWidget(self.fg_widget)
        self.page_widget.setFixedSize(600, 848)  # Approximate A4 ratio
        self.page_widget.setStyleSheet(
            "background-color: rgba(255, 255, 255, 200);"
            "color: black;"
            "border-radius: 15px;"
        )

        # Layout for the page widget: add margins for text
        page_layout = QVBoxLayout(self.page_widget)
        page_layout.setContentsMargins(50, 50, 50, 50)

        # Use the custom PlainTextEdit so that pasted text is unformatted
        self.editor = PlainTextEdit()
        self.editor.setPlainText(scene_text)
        self.editor.setStyleSheet(
            "background-color: transparent;"
            "color: black; font-size: 16pt;"
        )
        page_layout.addWidget(self.editor)

        fg_layout.addWidget(self.page_widget, alignment=Qt.AlignCenter)
        fg_layout.addStretch()

        layout.addWidget(self.fg_widget, 0, 0)

        # Raise the foreground widget so that it appears above the background
        self.fg_widget.raise_()

        # Load the first image if available
        self.load_current_image()

    def closeEvent(self, event):
        # When the window closes, if a callback has been set, pass the current text back.
        if callable(self.on_close):
            self.on_close(self.editor.toPlainText())
        event.accept()

    def load_current_image(self):
        if not self.image_files:
            self.bg_label.clear()
            return

        image_path = os.path.join(
            self.image_dir, self.image_files[self.current_index])
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.cycle_image()
            return

        # Set up fade-in transition
        opacity_effect = QGraphicsOpacityEffect()
        self.bg_label.setGraphicsEffect(opacity_effect)
        self.animation = QPropertyAnimation(opacity_effect, b"opacity")
        self.animation.setDuration(500)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.start()

        self.bg_label.setPixmap(pixmap)
        self.bg_label.repaint()

    def cycle_image(self):
        if not self.image_files:
            return
        self.current_index = (self.current_index + 1) % len(self.image_files)
        self.load_current_image()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_F11, Qt.Key_Escape):
            self.close()
        elif event.key() == Qt.Key_F12:
            self.cycle_image()
        else:
            super().keyPressEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    image_directory = os.path.join(os.getcwd(), "assets", "backgrounds")
    focus_mode = FocusMode(
        image_directory, scene_text="Your scene text here...")
    focus_mode.show()
    sys.exit(app.exec_())
