from PyQt5.QtWidgets import QWidget, QGroupBox, QFormLayout, QLineEdit, QComboBox, QTextEdit, QHBoxLayout, QPushButton, QCheckBox, QScrollArea, QVBoxLayout, QMessageBox, QFileDialog, QLabel
from PyQt5.QtGui import QFontMetrics
from internetarchive import upload, modify_metadata, delete
import re
from pathlib import Path

class ManageTab(QWidget):
    def __init__(self, session=None, parent=None):
        super().__init__(parent)
        self.session = session
        self.init_ui()

    def set_session(self, session):
        """Update the session object."""
        self.session = session

    def init_ui(self):
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Create a scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        # Create a widget for the scroll area
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)

        # File Upload section
        upload_group = QGroupBox("File Upload")
        upload_layout = QFormLayout()
        upload_group.setLayout(upload_layout)

        # Identifier input with validation
        self.upload_identifier = QLineEdit()
        self.upload_identifier.setPlaceholderText("Use only lowercase letters (a-z), numbers (0-9) and underscores (_). Keep it short & unique! (e.g., my_unique_identifier_01)")
        self.upload_identifier.textChanged.connect(self.validate_identifier)
        upload_layout.addRow("Identifier:", self.upload_identifier)

        # Identifier validation label
        self.identifier_status = QLabel("")
        upload_layout.addRow("", self.identifier_status)

        # Required metadata fields
        self.upload_title = QLineEdit()
        upload_layout.addRow("Title:", self.upload_title)

        # Mediatype combo box
        self.upload_mediatype = QComboBox()
        mediatypes = [
            "texts", "audio", "movies", "software", "image",
            "data", "web", "collection"
        ]
        self.upload_mediatype.addItems(mediatypes)
        upload_layout.addRow("Media Type:", self.upload_mediatype)

        # Collection input
        self.upload_collection = QLineEdit()
        self.upload_collection.setPlaceholderText("e.g., writing_way")
        upload_layout.addRow("Collection:", self.upload_collection)

        # Additional metadata
        self.upload_metadata = QTextEdit()
        self.upload_metadata.setPlaceholderText(
            "title:The Title of Your Book\n"
            "author:John Doe, Jane Smith (Last Name, First Name)\n"
            "subject:Fiction, Historical Fiction, Romance, Science Fiction (Comma separated keywords)\n"
            "description:A brief summary of your book's plot and themes.\n"
            "identifier:ISBN or OCLC number (if available - helps with matching existing records)\n"
            "language:en, pl, fr (ISO 639-1 code - e.g., en for English, pl for Polish)\n"
            "publisher:Publisher Name (e.g., Self-Published, Penguin Random House)\n"
            "date:YYYY-MM-DD (Year-Month-Day of publication - e.g., 2023-10-27)\n"
            "format:EPUB, MOBI, PDF (File format of your book)\n"
            "rights:Public Domain, Copyrighted (Specify copyright status)\n"
            "genre:Fiction, Non-fiction, Poetry, Drama (Book genre)\n"
            "series:Series Title (If part of a series)\n"
            "volume:Volume Number (e.g., 1, 2, 3 - if part of a multi-volume work)\n"
            "contributor:Editor, Illustrator, Translator (People who helped create the book)\n"
            "coverage:Geographical or temporal scope of the book's content.\n"
            "dedication:To whom the book is dedicated.\n"
            "notes:Any additional notes about the book (e.g., first edition, revised edition).\n"
        )

        # Dynamically calculate height based on number of placeholder lines
        placeholder = self.upload_metadata.placeholderText()
        line_count = placeholder.count('\n') + 1
        font_metrics = QFontMetrics(self.upload_metadata.font())
        line_height = font_metrics.lineSpacing()
        margins = (self.upload_metadata.contentsMargins().top() +
                   self.upload_metadata.contentsMargins().bottom())
        frame = self.upload_metadata.frameWidth() * 2
        desired_height = line_count * line_height + margins + frame

        self.upload_metadata.setFixedHeight(desired_height)
        upload_layout.addRow("Additional Metadata (key:value):", self.upload_metadata)

        # File selection
        file_selection_layout = QHBoxLayout()
        self.upload_file_btn = QPushButton("Choose Files")
        self.upload_file_btn.clicked.connect(lambda: self.select_upload_files(False))
        self.upload_dir_btn = QPushButton("Choose Folder")
        self.upload_dir_btn.clicked.connect(lambda: self.select_upload_files(True))
        file_selection_layout.addWidget(self.upload_file_btn)
        file_selection_layout.addWidget(self.upload_dir_btn)
        upload_layout.addRow("File Selection:", file_selection_layout)

        # Selected files display
        self.selected_files_label = QLabel("No files selected")
        self.selected_files_label.setWordWrap(True)
        upload_layout.addRow("Selected Files:", self.selected_files_label)

        # Upload button
        self.upload_btn = QPushButton("Upload")
        self.upload_btn.clicked.connect(self.perform_upload)
        upload_layout.addRow("", self.upload_btn)

        scroll_layout.addWidget(upload_group)

        # Metadata modification section
        metadata_group = QGroupBox("Metadata Modification")
        metadata_layout = QFormLayout()
        metadata_group.setLayout(metadata_layout)

        self.metadata_identifier = QLineEdit()
        metadata_layout.addRow("Identifier:", self.metadata_identifier)

        self.metadata_target = QComboBox()
        self.metadata_target.addItems(["metadata", "files/{filename}", "extra_metadata"])
        self.metadata_target.setEditable(True)
        metadata_layout.addRow("Modification Target:", self.metadata_target)

        self.metadata_key = QLineEdit()
        metadata_layout.addRow("Key:", self.metadata_key)

        self.metadata_value = QLineEdit()
        metadata_layout.addRow("Value:", self.metadata_value)

        self.metadata_operation = QComboBox()
        self.metadata_operation.addItems([
            "Replace",
            "Append to existing value",
            "Append to list",
            "Remove"
        ])
        metadata_layout.addRow("Operation:", self.metadata_operation)

        self.metadata_btn = QPushButton("Modify Metadata")
        self.metadata_btn.clicked.connect(self.modify_metadata)
        metadata_layout.addRow("", self.metadata_btn)

        scroll_layout.addWidget(metadata_group)

        # Delete files section
        delete_group = QGroupBox("File Deletion")
        delete_layout = QFormLayout()
        delete_group.setLayout(delete_layout)

        self.delete_identifier = QLineEdit()
        delete_layout.addRow("Identifier:", self.delete_identifier)

        self.delete_filename = QLineEdit()
        delete_layout.addRow("Filename:", self.delete_filename)

        self.cascade_delete = QCheckBox("Also delete derivative files")
        delete_layout.addRow("", self.cascade_delete)

        self.delete_btn = QPushButton("Delete File")
        self.delete_btn.clicked.connect(self.delete_file)
        delete_layout.addRow("", self.delete_btn)

        scroll_layout.addWidget(delete_group)

    def validate_identifier(self, text):
        """Validate that the identifier is in a valid format."""
        if text:
            if re.match(r'^[a-zA-Z0-9_\-]+$', text):
                self.identifier_status.setText("Valid identifier format")
                self.identifier_status.setStyleSheet("color: green;")
            else:
                self.identifier_status.setText("Invalid format! Use only: a-z, 0-9, _ and -")
                self.identifier_status.setStyleSheet("color: red;")
        else:
            self.identifier_status.setText("")

    def select_upload_files(self, is_dir=False):
        """Select files or a directory to upload."""
        if is_dir:
            folder_path = QFileDialog.getExistingDirectory(self, "Choose Folder")
            if folder_path:
                self.upload_file_paths = [str(path) for path in Path(folder_path).rglob('*') if path.is_file()]
                self.selected_files_label.setText(f"Selected {len(self.upload_file_paths)} files from folder: {folder_path}")
        else:
            file_paths, unused = QFileDialog.getOpenFileNames(self, "Choose Files")
            if file_paths:
                self.upload_file_paths = file_paths
                self.selected_files_label.setText(f"Selected {len(file_paths)} files")

    def perform_upload(self):
        """Upload selected files to Internet Archive."""
        if not hasattr(self, 'upload_file_paths') or not self.upload_file_paths:
            QMessageBox.warning(self, "Warning", "Select files or a folder to upload")
            return
            
        identifier = self.upload_identifier.text().strip()
        if not identifier:
            QMessageBox.warning(self, "Warning", "Identifier is required")
            return
            
        if not re.match(r'^[a-zA-Z0-9_\-]+$', identifier):
            QMessageBox.warning(self, "Error", "Invalid identifier format. Use only characters: a-z, 0-9, _ and -")
            return
            
        metadata = {}
        metadata['title'] = self.upload_title.text().strip()
        metadata['mediatype'] = self.upload_mediatype.currentText()
        
        if self.upload_collection.text().strip():
            metadata['collection'] = self.upload_collection.text().strip()
            
        additional_metadata = self.upload_metadata.toPlainText().strip()
        if additional_metadata:
            for line in additional_metadata.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata[key.strip()] = value.strip()
        
        total_size = sum(os.path.getsize(file) for file in self.upload_file_paths)
        if total_size > 100 * 1024 * 1024 * 1024:
            response = QMessageBox.question(
                self,
                "Large Upload",
                "You have selected files with a total size over 100GB. According to Archive.org recommendations, items should not exceed 100GB. Do you want to continue?",
                QMessageBox.Yes | QMessageBox.No
            )
            if response == QMessageBox.No:
                return
                
        if len(self.upload_file_paths) > 10000:
            response = QMessageBox.question(
                self,
                "Too Many Files",
                "You have selected over 10,000 files. According to Archive.org recommendations, items should not contain more than 10,000 files. Do you want to continue?",
                QMessageBox.Yes | QMessageBox.No
            )
            if response == QMessageBox.No:
                return
        
        try:
            if self.session:
                upload(identifier, files=self.upload_file_paths, metadata=metadata, archive_session=self.session)
            else:
                upload(identifier, files=self.upload_file_paths, metadata=metadata)
                
            QMessageBox.information(self, "Success", "Files have been successfully uploaded")
            
            self.upload_identifier.clear()
            self.upload_title.clear()
            self.upload_collection.clear()
            self.upload_metadata.clear()
            self.selected_files_label.setText("No files selected")
            delattr(self, 'upload_file_paths')
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Upload failed: {str(e)}")

    def modify_metadata(self):
        """Modify metadata for the specified item."""
        identifier = self.metadata_identifier.text().strip()
        key = self.metadata_key.text().strip()
        value = self.metadata_value.text().strip()
        target = self.metadata_target.currentText().strip()
        operation = self.metadata_operation.currentText()
        
        if not identifier or not key:
            QMessageBox.warning(self, "Warning", "Identifier and key are required")
            return
            
        append = False
        append_list = False
        
        if operation == "Append to existing value":
            append = True
        elif operation == "Append to list":
            append_list = True
        elif operation == "Remove":
            value = "REMOVE_TAG"
                
        if target.startswith("files/") and "{filename}" in target:
            filename, ok = QFileDialog.getOpenFileName(self, "Choose target file", "", "All Files (*)")
            if ok and filename:
                basename = os.path.basename(filename)
                target = target.replace("{filename}", basename)
            else:
                QMessageBox.warning(self, "Warning", "No target file selected")
                return
            
        try:
            if self.session:
                response = modify_metadata(
                    identifier,
                    metadata={key: value},
                    target=target if target != "metadata" else None,
                    append=append,
                    append_list=append_list,
                    archive_session=self.session
                )
            else:
                response = modify_metadata(
                    identifier,
                    metadata={key: value},
                    target=target if target != "metadata" else None,
                    append=append,
                    append_list=append_list
                )
                
            if response.status_code == 200:
                QMessageBox.information(self, "Success", "Metadata has been successfully modified")
            else:
                QMessageBox.warning(self, "Warning", f"Server error: {response.status_code} - {response.text}")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Metadata modification failed: {str(e)}")

    def delete_file(self):
        """Delete a file from an Archive.org item."""
        identifier = self.delete_identifier.text().strip()
        filename = self.delete_filename.text().strip()
        cascade = self.cascade_delete.isChecked()
        
        if not identifier or not filename:
            QMessageBox.warning(self, "Warning", "Identifier and filename are required")
            return
            
        response = QMessageBox.question(
            self,
            "Delete Confirmation",
            f"Are you sure you want to delete the file '{filename}' from item '{identifier}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if response == QMessageBox.No:
            return
            
        try:
            if self.session:
                response = delete(
                    identifier,
                    files=filename,
                    cascade_delete=cascade,
                    archive_session=self.session
                )
            else:
                response = delete(
                    identifier,
                    files=filename,
                    cascade_delete=cascade
                )
                
            if all(r.status_code == 200 for r in response):
                QMessageBox.information(self, "Success", "File was successfully deleted")
                self.delete_filename.clear()
            else:
                failed_responses = [f"{r.status_code}: {r.text}" for r in response if r.status_code != 200]
                failed_messages = "\n".join(failed_responses)
                QMessageBox.warning(
                    self,
                    "Warning",
                    f"Some delete operations failed:\n{failed_messages}"
                )
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"File deletion failed: {str(e)}")