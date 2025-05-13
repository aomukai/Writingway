from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QFrame,
                            QFormLayout, QMessageBox, QCheckBox, QApplication, QHBoxLayout)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QCursor
from internetarchive import get_session, configure
import configparser
import os
import re
import webbrowser

class LoginTab(QWidget):
    login_successful = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.load_remembered_login()
        self.check_login_status()

    def init_ui(self):
        # Main layout setup with proper spacing
        self.layout = QVBoxLayout()
        self.layout.setSpacing(10)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(self.layout)
        
        # Title and header
        title_label = QLabel("Internet Archive Login")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(title_label)
        
        # Information and warning in a framed box
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.StyledPanel)
        info_frame.setStyleSheet("background-color: #F5F5F5; border-radius: 5px;")
        info_layout = QVBoxLayout(info_frame)
        
        self.info_label = QLabel("Note: To access the full functionality, you must log in every time you launch the Internet Archive window.")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)
        
        self.security_warning = QLabel("Warning: The internetarchive library stores login data in a configuration file on your computer. Make sure you are using a secure machine.")
        self.security_warning.setWordWrap(True)
        self.security_warning.setStyleSheet("color: #FF5722;")
        info_layout.addWidget(self.security_warning)
        
        self.layout.addWidget(info_frame)
        self.layout.addSpacing(10)
        
        # Form layout for credentials
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form_layout.setLabelAlignment(Qt.AlignRight)
        
        # Email input with validation
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("example@domain.com")
        self.username_input.returnPressed.connect(self.perform_login)
        form_layout.addRow("Email:", self.username_input)
        
        # Password input
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.returnPressed.connect(self.perform_login)
        form_layout.addRow("Password:", self.password_input)
        
        # Add form to main layout
        form_frame = QFrame()
        form_frame.setLayout(form_layout)
        self.layout.addWidget(form_frame)
        
        # Checkbox options in horizontal layout
        checkbox_frame = QFrame()
        checkbox_layout = QHBoxLayout(checkbox_frame)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        
        # Remember email checkbox
        self.remember_email_cb = QCheckBox("Remember my Email")
        checkbox_layout.addWidget(self.remember_email_cb)
        
        # Remember password checkbox with additional warning
        self.remember_password_cb = QCheckBox("Remember Password (Security Risk)")
        self.remember_password_cb.setToolTip("Saving passwords is a security risk. Only use on private, secure devices.")
        checkbox_layout.addWidget(self.remember_password_cb)
        
        self.layout.addWidget(checkbox_frame)
        
        # Login button in its own container with padding
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(50, 10, 50, 10)
        
        self.login_btn = QPushButton("Log In")
        self.login_btn.setMinimumHeight(35)
        self.login_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.login_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; border-radius: 5px;")
        self.login_btn.clicked.connect(self.perform_login)
        button_layout.addWidget(self.login_btn)
        
        self.layout.addWidget(button_container)
        
        # Account links layout (forgot password & register) in horizontal layout
        account_links_frame = QFrame()
        account_links_layout = QHBoxLayout(account_links_frame)
        account_links_layout.setAlignment(Qt.AlignCenter)
        account_links_layout.setContentsMargins(0, 0, 0, 0)
        
        # Forgot password link
        self.forgot_password_btn = QPushButton("Forgot Password?")
        self.forgot_password_btn.setStyleSheet("border: none; text-decoration: underline; color: blue;")
        self.forgot_password_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.forgot_password_btn.clicked.connect(self.open_forgot_password)
        account_links_layout.addWidget(self.forgot_password_btn)
        
        # Registration link
        self.register_btn = QPushButton("Register")
        self.register_btn.setStyleSheet("border: none; text-decoration: underline; color: blue;")
        self.register_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.register_btn.clicked.connect(self.open_registration)
        account_links_layout.addWidget(self.register_btn)
        
        self.layout.addWidget(account_links_frame)
        
        # Status label at the bottom
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.status_label)
        
        # Add stretch at the end to push all content up
        self.layout.addStretch()
        
        # Set minimum size for the dialog
        self.setMinimumWidth(450)

    def check_login_status(self):
        """Check if user is already logged in by examining the config file."""
        try:
            config_paths = [
                os.path.expanduser("~/.ia"),
                os.path.expanduser("~/.config/ia.ini")
            ]
            
            for path in config_paths:
                if os.path.exists(path):
                    config = configparser.ConfigParser()
                    config.read(path)
                    if config.has_section('cookies') and 'logged-in-user' in config['cookies']:
                        user = config['cookies']['logged-in-user']
                        user = user.replace('%40', '@')
                        self.status_label.setText(f"Status: Logged in as {user}")
                        self.status_label.setStyleSheet("color: green;")
                        return
                    
            self.status_label.setText("Status: Not logged in")
            self.status_label.setStyleSheet("color: red;")
        except Exception as e:
            self.status_label.setText(f"Status: Unknown (Error: {str(e)})")
            self.status_label.setStyleSheet("color: orange;")

    def validate_email(self, email):
        """Simple email validation using regex pattern."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def perform_login(self):
        """Handle the login process with validation and error handling."""
        # Get credentials from input fields
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        # Basic validation
        if not username or not password:
            QMessageBox.warning(self, "Error", "Email and password cannot be empty.")
            return
            
        # Email format validation
        if not self.validate_email(username):
            QMessageBox.warning(self, "Error", "Please enter a valid email address.")
            return
            
        # Change cursor to indicate processing
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        try:
            # Attempt to log in
            configure(username, password)
            session = get_session()
            # Test the connection with a simple request
            session.get_item('nasa')
            
            # Save login credentials if checkboxes are checked
            self.save_remembered_login(username, password if self.remember_password_cb.isChecked() else None)
            
            # Update status
            self.status_label.setText(f"Status: Logged in as {username}")
            self.status_label.setStyleSheet("color: green;")
            QMessageBox.information(self, "Success", "Successfully logged in to Archive.org!")
            self.login_successful.emit()
            
        except Exception as e:
            # Specific error handling
            error_msg = str(e).lower()
            if "401" in error_msg or "unauthorized" in error_msg:
                QMessageBox.critical(self, "Login Failed", "Invalid email or password. Please check your credentials and try again.")
            elif "connection" in error_msg or "timeout" in error_msg or "network" in error_msg:
                QMessageBox.critical(self, "Connection Error", 
                                    "Could not connect to Archive.org. Please check your internet connection and try again.")
            else:
                QMessageBox.critical(self, "Error", f"Login failed: {e}")
                
            self.status_label.setText("Status: Login error")
            self.status_label.setStyleSheet("color: red;")
        finally:
            # Always restore cursor
            QApplication.restoreOverrideCursor()
            
    def open_forgot_password(self):
        """Open the forgot password page in the default web browser."""
        webbrowser.open("https://archive.org/account/forgot-password")
        
    def open_registration(self):
        """Open the registration page in the default web browser."""
        webbrowser.open("https://archive.org/account/signup")
            
    def load_remembered_login(self):
        """Load saved login credentials if they exist."""
        path = os.path.expanduser("~/.config/ia.ini")
        cfg = configparser.ConfigParser()
        if os.path.exists(path):
            cfg.read(path)
            if cfg.has_section('remember'):
                # Load username if saved
                if cfg['remember'].get('username'):
                    self.username_input.setText(cfg['remember']['username'])
                    self.remember_email_cb.setChecked(True)
                
                # Load password if saved
                if cfg['remember'].get('password'):
                    self.password_input.setText(cfg['remember']['password'])
                    self.remember_password_cb.setChecked(True)

    def save_remembered_login(self, username=None, password=None):
        """Save login credentials based on checkbox selections."""
        path = os.path.expanduser("~/.config/ia.ini")
        cfg = configparser.ConfigParser()
        
        # Load existing config if it exists
        if os.path.exists(path):
            cfg.read(path)
            
        # Create remember section if it doesn't exist
        if not cfg.has_section('remember'):
            cfg.add_section('remember')
            
        # Handle email remembering
        if self.remember_email_cb.isChecked() and username:
            cfg.set('remember', 'username', username)
        else:
            cfg.remove_option('remember', 'username')
            
        # Handle password remembering
        if password:  # Only if password is provided and checkbox is checked
            cfg.set('remember', 'password', password)
        else:
            cfg.remove_option('remember', 'password')
            
        # Write updated config to file
        with open(path, 'w') as f:
            cfg.write(f)