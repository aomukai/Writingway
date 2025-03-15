#!/usr/bin/env python3
from PyQt5.QtWidgets import (
    QSplitter, QTreeWidget, QTextEdit, QToolBar, QAction, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QComboBox, QStackedWidget, QFontComboBox, QLabel, QCheckBox
)
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtCore import Qt
from context_panel import ContextPanel
from theme_manager import ThemeManager
from focus_mode import PlainTextEdit

def build_main_ui(window):
    # Ensure the main window has a current_theme attribute; default to "Standard" if not set.
    if not hasattr(window, "current_theme"):
        window.current_theme = "Standard"
    # Determine the tint color using the explicit mapping.
    tint_str = ThemeManager.ICON_TINTS.get(window.current_theme, "black")
    tint = QColor(tint_str)
    # store the tint for later use (e.g. in status icons)
    window.icon_tint = tint

    window.setStatusBar(window.statusBar())

    # Global Actions Toolbar (always visible)
    global_toolbar = QToolBar("Global Actions")
    window.addToolBar(global_toolbar)

    window.compendium_action = QAction(window.get_tinted_icon(
        "assets/icons/book.svg", tint_color=tint), "", window)
    window.compendium_action.setToolTip(
        "Compendium: Toggle the embedded compendium panel to view/edit your worldbuilding database")
    window.compendium_action.triggered.connect(window.open_compendium)
    global_toolbar.addAction(window.compendium_action)

    window.prompt_options_action = QAction(window.get_tinted_icon(
        "assets/icons/settings.svg", tint_color=tint), "", window)
    window.prompt_options_action.setToolTip(
        "Prompt Options: Configure your writing prompts and LLM settings")
    window.prompt_options_action.triggered.connect(window.open_prompts_window)
    global_toolbar.addAction(window.prompt_options_action)

    window.workshop_action = QAction(window.get_tinted_icon(
        "assets/icons/message-square.svg", tint_color=tint), "", window)
    window.workshop_action.setToolTip("Workshop Chat: Opens the Workshop Chat")
    window.workshop_action.triggered.connect(window.open_workshop)
    global_toolbar.addAction(window.workshop_action)

    window.focus_mode_action = QAction(window.get_tinted_icon(
        "assets/icons/maximize-2.svg", tint_color=tint), "", window)
    window.focus_mode_action.setToolTip("Focus Mode: Enter Focus Mode")
    window.focus_mode_action.triggered.connect(window.open_focus_mode)
    global_toolbar.addAction(window.focus_mode_action)

    # -----------------------------------------------------
    # Remove the previous top settings layout.
    # -----------------------------------------------------

    # -----------------------------------------------------
    # New Layout Structure:
    # The main window will be divided horizontally into two parts:
    #   Left: Project Tree
    #   Right: A vertical splitter that contains:
    #         (a) Top: A horizontal splitter with the compendium panel and scene editor
    #         (b) Bottom: The bottom stack (LLM preview, action beats, etc.)
    # -----------------------------------------------------
    main_splitter = QSplitter(Qt.Horizontal)

    # --- Left Panel: Project Tree ---
    window.tree = QTreeWidget()
    window.tree.setHeaderLabel("Project Structure")
    window.tree.setContextMenuPolicy(Qt.CustomContextMenu)
    window.tree.customContextMenuRequested.connect(window.show_tree_context_menu)
    window.populate_tree()
    window.tree.currentItemChanged.connect(window.tree_item_changed)
    main_splitter.addWidget(window.tree)

    # --- Right Panel: Vertical Splitter ---
    right_vertical_splitter = QSplitter(Qt.Vertical)

    # ---- Top Row: Horizontal Splitter for Compendium and Scene Editor ----
    top_horizontal_splitter = QSplitter(Qt.Horizontal)

    # Import and create the compendium panel (initially hidden)
    from compendium_panel import CompendiumPanel
    window.compendium_panel = CompendiumPanel(window)
    window.compendium_panel.setVisible(False)  # Toggle with the compendium button
    top_horizontal_splitter.addWidget(window.compendium_panel)

    # Scene Editor Area (with its editor toolbar)
    editor_container = QWidget()
    editor_layout = QVBoxLayout(editor_container)

    # Editor Toolbar: Merges formatting actions and scene-specific controls
    editor_toolbar = QToolBar("Editor Toolbar", window)

    # --- Formatting Actions ---
    window.bold_action = QAction(window.get_tinted_icon(
        "assets/icons/bold.svg", tint_color=tint), "", window)
    window.bold_action.setToolTip("Bold")
    window.bold_action.setCheckable(True)
    window.bold_action.triggered.connect(window.toggle_bold)
    editor_toolbar.addAction(window.bold_action)

    window.italic_action = QAction(window.get_tinted_icon(
        "assets/icons/italic.svg", tint_color=tint), "", window)
    window.italic_action.setToolTip("Italic")
    window.italic_action.setCheckable(True)
    window.italic_action.triggered.connect(window.toggle_italic)
    editor_toolbar.addAction(window.italic_action)

    window.underline_action = QAction(window.get_tinted_icon(
        "assets/icons/underline.svg", tint_color=tint), "", window)
    window.underline_action.setToolTip("Underline")
    window.underline_action.setCheckable(True)
    window.underline_action.triggered.connect(window.toggle_underline)
    editor_toolbar.addAction(window.underline_action)

    # Separator between text styling and TTS actions
    editor_toolbar.addSeparator()

    window.tts_action = QAction(window.get_tinted_icon(
        "assets/icons/play-circle.svg", tint_color=tint), "", window)
    window.tts_action.setToolTip("Play TTS (or Stop if playing)")
    window.tts_action.triggered.connect(window.toggle_tts)
    editor_toolbar.addAction(window.tts_action)

    # Separator between TTS and alignment actions
    editor_toolbar.addSeparator()

    window.align_left_action = QAction(window.get_tinted_icon(
        "assets/icons/align-left.svg", tint_color=tint), "", window)
    window.align_left_action.setToolTip("Align Left")
    window.align_left_action.triggered.connect(window.align_left)
    editor_toolbar.addAction(window.align_left_action)

    window.align_center_action = QAction(window.get_tinted_icon(
        "assets/icons/align-center.svg", tint_color=tint), "", window)
    window.align_center_action.setToolTip("Center Align")
    window.align_center_action.triggered.connect(window.align_center)
    editor_toolbar.addAction(window.align_center_action)

    window.align_right_action = QAction(window.get_tinted_icon(
        "assets/icons/align-right.svg", tint_color=tint), "", window)
    window.align_right_action.setToolTip("Align Right")
    window.align_right_action.triggered.connect(window.align_right)
    editor_toolbar.addAction(window.align_right_action)

    # Font selection widgets as part of the toolbar
    from PyQt5.QtWidgets import QFontComboBox
    font_combo = QFontComboBox()
    font_combo.setToolTip("Select a font")
    font_combo.currentFontChanged.connect(lambda font: window.editor.setCurrentFont(font))
    editor_toolbar.addWidget(font_combo)

    font_size_combo = QComboBox()
    font_sizes = [10, 12, 14, 16, 18, 20, 24, 28, 32]
    for size in font_sizes:
        font_size_combo.addItem(str(size))
    font_size_combo.setCurrentText("12")
    font_size_combo.setToolTip("Select font size")
    font_size_combo.currentIndexChanged.connect(lambda: window.set_font_size(int(font_size_combo.currentText())))
    editor_toolbar.addWidget(font_size_combo)

    # Separator between formatting and scene-specific controls
    editor_toolbar.addSeparator()

    # Scene-Specific Actions
    window.manual_save_action = QAction(window.get_tinted_icon(
        "assets/icons/save.svg", tint_color=tint), "", window)
    window.manual_save_action.setToolTip("Manual Save: Manually save the current scene")
    window.manual_save_action.triggered.connect(window.manual_save_scene)
    editor_toolbar.addAction(window.manual_save_action)

    window.oh_shit_action = QAction(window.get_tinted_icon(
        "assets/icons/share.svg", tint_color=tint), "", window)
    window.oh_shit_action.setToolTip("Oh Shit: Show backup versions for this scene")
    window.oh_shit_action.triggered.connect(window.on_oh_shit)
    editor_toolbar.addAction(window.oh_shit_action)

    # NEW: Analysis Editor Button
    window.analysis_editor_action = QAction(window.get_tinted_icon(
        "assets/icons/feather.svg", tint_color=tint), "", window)
    window.analysis_editor_action.setToolTip("Open Analysis Editor")
    window.analysis_editor_action.triggered.connect(window.open_analysis_editor)
    editor_toolbar.addAction(window.analysis_editor_action)

    # -----------------------------------------------------
    # NEW: Add a divider then add the pulldowns next to the feather icon.
    # Create a container widget with a horizontal layout for the pulldowns.
    editor_toolbar.addSeparator()
    pulldown_container = QWidget()
    pulldown_layout = QHBoxLayout(pulldown_container)
    pulldown_layout.setContentsMargins(0, 0, 0, 0)  # Remove extra margins

    # Create POV pulldown
    window.pov_combo = QComboBox()
    window.pov_combo.addItems(["First Person", "Third Person Limited", "Omniscient", "Custom..."])
    window.pov_combo.setToolTip(f"POV: {window.current_pov if hasattr(window, 'current_pov') and window.current_pov else 'Not Set'}")
    window.pov_combo.currentIndexChanged.connect(window.handle_pov_change)
    pulldown_layout.addWidget(QLabel("POV:"))
    pulldown_layout.addWidget(window.pov_combo)

    # Create POV Character pulldown
    window.pov_character_combo = QComboBox()
    window.pov_character_combo.addItems(["Alice", "Bob", "Charlie", "Custom..."])
    window.pov_character_combo.setToolTip(f"POV Character: {window.current_pov_character if hasattr(window, 'current_pov_character') and window.current_pov_character else 'Not Set'}")
    window.pov_character_combo.currentIndexChanged.connect(window.handle_pov_character_change)
    pulldown_layout.addWidget(QLabel("POV Character:"))
    pulldown_layout.addWidget(window.pov_character_combo)

    # Create Tense pulldown
    window.tense_combo = QComboBox()
    window.tense_combo.addItems(["Past Tense", "Present Tense", "Custom..."])
    window.tense_combo.setToolTip(f"Tense: {window.current_tense if hasattr(window, 'current_tense') and window.current_tense else 'Not Set'}")
    window.tense_combo.currentIndexChanged.connect(window.handle_tense_change)
    pulldown_layout.addWidget(QLabel("Tense:"))
    pulldown_layout.addWidget(window.tense_combo)

    # Add the pulldown container to the toolbar
    editor_toolbar.addWidget(pulldown_container)

    # Add the Editor Toolbar above the scene editor
    editor_layout.addWidget(editor_toolbar)

    # Scene Editor
    window.editor = PlainTextEdit()
    window.editor.setPlaceholderText("Select a node to edit its content...")
    window.editor.setContextMenuPolicy(Qt.CustomContextMenu)
    window.editor.customContextMenuRequested.connect(window.show_editor_context_menu)
    window.editor.setStyleSheet("border: 1px solid #ccc; padding: 2px;")
    editor_layout.addWidget(window.editor)

    # Add the top_horizontal_splitter's second widget: the editor container
    top_horizontal_splitter.addWidget(editor_container)
    top_horizontal_splitter.setStretchFactor(0, 1)  # Compendium Panel
    top_horizontal_splitter.setStretchFactor(1, 3)  # Editor Area

    # ---- Bottom Row: Bottom Stack (Summary panel, LLM preview, and Action Beats) ----
    window.bottom_stack = QStackedWidget()

    # Summary panel
    window.summary_panel = QWidget()
    summary_layout = QHBoxLayout(window.summary_panel)
    summary_layout.addStretch()
    window.create_summary_button = QPushButton("Create Summary")
    window.create_summary_button.clicked.connect(window.create_summary)
    summary_layout.addWidget(window.create_summary_button)
    window.save_summary_button = QPushButton("Save Summary")
    window.save_summary_button.clicked.connect(window.save_summary)
    summary_layout.addWidget(window.save_summary_button)
    summary_layout.addStretch()

    # LLM panel (with re-ordered layout)
    window.llm_panel = QWidget()
    llm_layout = QVBoxLayout(window.llm_panel)

    # Preview Group (Middle)
    preview_group = QWidget()
    preview_layout = QVBoxLayout(preview_group)
    window.preview_text = QTextEdit()
    window.preview_text.setReadOnly(True)
    window.preview_text.setPlaceholderText("LLM output preview will appear here...")
    preview_layout.addWidget(window.preview_text)
    preview_button_layout = QHBoxLayout()
    window.apply_button = QPushButton()
    window.apply_button.setIcon(window.get_tinted_icon("assets/icons/save.svg", tint_color=tint))
    window.apply_button.setToolTip("Appends the LLM's output to your current scene")
    window.apply_button.clicked.connect(window.apply_preview)
    preview_button_layout.addWidget(window.apply_button)

    # New: Checkbox to include Action Beats (prompt) with the LLM output
    window.include_prompt_checkbox = QCheckBox("Include Action Beats")
    window.include_prompt_checkbox.setToolTip("Include the text from the Action Beats field in the scene text")
    window.include_prompt_checkbox.setChecked(True)
    preview_button_layout.addWidget(window.include_prompt_checkbox)

    preview_button_layout.addStretch()

    preview_layout.addLayout(preview_button_layout)
    llm_layout.addWidget(preview_group)

    # Action Beats Group (Bottom)
    action_group = QWidget()
    action_layout = QHBoxLayout(action_group)
    left_container = QWidget()
    left_layout = QVBoxLayout(left_container)
    window.prompt_input = PlainTextEdit()
    window.prompt_input.setPlaceholderText("Enter your action beats here...")
    window.prompt_input.setMinimumHeight(100)
    left_layout.addWidget(window.prompt_input)
    left_buttons_layout = QHBoxLayout()
    window.prompt_dropdown = QComboBox()
    window.prompt_dropdown.setToolTip("Select a prose prompt")
    window.prompt_dropdown.addItem("Select Prose Prompt")
    window.prompt_dropdown.currentIndexChanged.connect(window.prompt_dropdown_changed)
    left_buttons_layout.addWidget(window.prompt_dropdown)
    window.send_button = QPushButton()
    window.send_button.setIcon(window.get_tinted_icon("assets/icons/send.svg", tint_color=tint))
    window.send_button.setToolTip("Sends the action beats to the LLM")
    window.send_button.clicked.connect(window.send_prompt)
    left_buttons_layout.addWidget(window.send_button)
    window.stop_button = QPushButton()
    window.stop_button.setIcon(window.get_tinted_icon("assets/icons/x-octagon.svg", tint_color=tint))
    window.stop_button.setToolTip("Stop the LLM processing")
    window.stop_button.clicked.connect(window.stop_llm)
    window.stop_button.setEnabled(False)
    left_buttons_layout.addWidget(window.stop_button)
    window.context_toggle_button = QPushButton()
    window.context_toggle_button.setIcon(window.get_tinted_icon("assets/icons/book.svg", tint_color=tint))
    window.context_toggle_button.setToolTip("Lets you decide which additional information to send with the prompt")
    window.context_toggle_button.setCheckable(True)
    def toggle_context():
        window.toggle_context_panel()
        window.context_toggle_button.setText("")
        if window.context_panel.isVisible():
            window.context_toggle_button.setIcon(window.get_tinted_icon("assets/icons/book-open.svg", tint_color=tint))
        else:
            window.context_toggle_button.setIcon(window.get_tinted_icon("assets/icons/book.svg", tint_color=tint))
    window.context_toggle_button.clicked.connect(toggle_context)
    left_buttons_layout.addWidget(window.context_toggle_button)
    window.model_indicator = QLabel("")
    window.model_indicator.setStyleSheet("font-weight: bold; padding-left: 10px;")
    window.model_indicator.setToolTip("Selected prompt's model")
    left_buttons_layout.addWidget(window.model_indicator)
    left_buttons_layout.addStretch()
    left_layout.addLayout(left_buttons_layout)
    left_layout.addStretch()
    action_layout.addWidget(left_container, stretch=2)
    window.context_panel = ContextPanel(window.structure, window.project_name)
    window.context_panel.setVisible(False)
    action_layout.addWidget(window.context_panel, stretch=1)
    llm_layout.addWidget(action_group)

    # Add panels to the bottom stack
    window.bottom_stack.addWidget(window.summary_panel)
    window.bottom_stack.addWidget(window.llm_panel)

    # Assemble the right vertical splitter:
    right_vertical_splitter.addWidget(top_horizontal_splitter)  # Top: compendium + scene editor
    right_vertical_splitter.addWidget(window.bottom_stack)        # Bottom: LLM preview and action beats
    right_vertical_splitter.setStretchFactor(0, 3)
    right_vertical_splitter.setStretchFactor(1, 1)

    # Add the left panel (project tree) and the right vertical splitter to the main splitter
    main_splitter.addWidget(window.tree)
    main_splitter.addWidget(right_vertical_splitter)
    main_splitter.setStretchFactor(0, 1)  # Project Tree
    main_splitter.setStretchFactor(1, 3)  # Right Side

    # Instead of wrapping in a container with top settings, just use the main splitter now.
    window.main_splitter = main_splitter
    window.setCentralWidget(main_splitter)
