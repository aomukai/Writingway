import sys
import os
import json
import subprocess
import warnings
import datetime
import tempfile
import time
import numpy as np
import noisereduce as nr
import shutil  # Added for FFmpeg check
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QUrl, QTimer
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QTextEdit, QFileDialog, QLabel, QMessageBox, QSplitter,
    QDialog, QListWidget, QGridLayout, QSlider, QStyle, QAction,
    QListWidgetItem, QFrame, QWidget, QCheckBox, QSpinBox, QGroupBox
)
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
import pyaudio
import wave
import whisper
from pydub import AudioSegment  # For audio processing
from moviepy.video.io.VideoFileClip import VideoFileClip
from settings.theme_manager import ThemeManager

# Suppress FP16 warning for CPU usage
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU; using FP32 instead")

# ------------------------------ Model Download Dialog ------------------------------
class ModelDownloadThread(QThread):
    # Signal emitted when the download is finished
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, model_name):
        super().__init__()
        self.model_name = model_name

    def run(self):
        try:
            whisper.load_model(self.model_name)
            self.finished_signal.emit(True, self.model_name)
        except Exception as e:
            self.finished_signal.emit(False, str(e))

class ModelDownloadDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Whisper Models")
        self.setMinimumWidth(500)
        self.setMinimumHeight(350)
        
        layout = QVBoxLayout()
        intro_label = QLabel("Select models to download:")
        intro_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(intro_label)
        
        self.model_list = QListWidget()
        self.model_list.setAlternatingRowColors(True)
        models = [
            ("tiny", "Tiny (39M parameters) - Fastest, least accurate"),
            ("base", "Base (74M parameters) - Fast with decent accuracy"),
            ("small", "Small (244M parameters) - Balanced speed/accuracy"),
            ("medium", "Medium (769M parameters) - Good accuracy, slower"),
            ("large", "Large (1550M parameters) - Best accuracy, slowest"),
            ("turbo", "Turbo (809M parameters) - Optimized for speed")
        ]
        for model_name, description in models:
            item_text = f"{model_name}: {description}"
            if self.model_exists(model_name):
                item_text += " [DOWNLOADED]"
            self.model_list.addItem(item_text)
        
        layout.addWidget(self.model_list)
        
        button_layout = QHBoxLayout()
        btn_download = QPushButton("Download Selected Model")
        btn_download.clicked.connect(self.download_model)
        button_layout.addWidget(btn_download)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        button_layout.addWidget(btn_close)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def model_exists(self, model_name):
        cache_dir = os.path.expanduser("~/.cache/whisper")
        model_file = os.path.join(cache_dir, f"{model_name}.pt")
        return os.path.exists(model_file)
    
    def download_model(self):
        selected_items = self.model_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a model to download.")
            return
        selected_item = selected_items[0].text()
        model_name = selected_item.split(':')[0]
        if "[DOWNLOADED]" in selected_item:
            QMessageBox.information(self, "Already Downloaded", f"The model '{model_name}' is already downloaded.")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Download",
            f"Are you sure you want to download the '{model_name}' model? This may take some time.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            self.start_download_thread(model_name)

    def start_download_thread(self, model_name):
        self.download_thread = ModelDownloadThread(model_name)
        self.download_thread.finished_signal.connect(self.on_download_finished)
        self.download_thread.start()
        QMessageBox.information(self, "Download Started", f"Downloading the model '{model_name}' in the background.")

    def on_download_finished(self, success, result):
        if success:
            current_index = self.model_list.currentRow()
            selected_text = self.model_list.item(current_index).text()
            if "[DOWNLOADED]" not in selected_text:
                self.model_list.item(current_index).setText(f"{selected_text} [DOWNLOADED]")
            QMessageBox.information(self, "Download Complete", f"The model '{result}' has been downloaded successfully.")
        else:
            QMessageBox.critical(self, "Download Error", f"Failed to download model: {result}")

# ----------------------- Transcription History Dialog -----------------------
class TranscriptionHistoryDialog(QDialog):
    transcription_selected = pyqtSignal(dict)
    
    def __init__(self, history_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Transcription History")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.history_data = history_data
        
        layout = QVBoxLayout()
        header_label = QLabel("Previous Transcriptions")
        header_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(header_label)
        
        self.history_list = QListWidget()
        self.history_list.setAlternatingRowColors(True)
        self.history_list.itemDoubleClicked.connect(self.load_transcription)
        self.populate_history_list()
        layout.addWidget(self.history_list)
        
        button_layout = QHBoxLayout()
        self.btn_load = QPushButton("Load Selected")
        self.btn_load.clicked.connect(self.load_transcription)
        button_layout.addWidget(self.btn_load)
        
        self.btn_delete = QPushButton("Delete Selected")
        self.btn_delete.clicked.connect(self.delete_transcription)
        button_layout.addWidget(self.btn_delete)
        
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        button_layout.addWidget(self.btn_close)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def populate_history_list(self):
        self.history_list.clear()
        sorted_history = sorted(self.history_data, key=lambda x: x.get('timestamp', ''), reverse=True)
        for idx, item in enumerate(sorted_history):
            timestamp = item.get('timestamp', 'Unknown date')
            filename = item.get('filename', 'Unknown file')
            model = item.get('model', 'Unknown model')
            display_text = f"{timestamp} - {filename} (Model: {model})"
            
            # Create list widget item with checkbox
            list_item = QListWidgetItem()
            list_item.setData(Qt.UserRole, idx)
            
            # Create widget for the item with checkbox and label
            item_widget = QWidget()
            item_layout = QHBoxLayout()
            item_layout.setContentsMargins(5, 2, 5, 2)
            
            checkbox = QCheckBox()
            label = QLabel(display_text)
            
            item_layout.addWidget(checkbox)
            item_layout.addWidget(label)
            item_layout.addStretch()
            
            item_widget.setLayout(item_layout)
            
            # Set the custom widget for this item
            self.history_list.addItem(list_item)
            self.history_list.setItemWidget(list_item, item_widget)
            
            # Store the checkbox reference in the item's data for later access
            list_item.setData(Qt.UserRole + 1, checkbox)
    
    def load_transcription(self):
        selected_item = None
        
        # Find the first selected item (with checkbox or directly selected)
        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            checkbox = item.data(Qt.UserRole + 1)
            
            if checkbox.isChecked() or item.isSelected():
                selected_item = item
                break
        
        if not selected_item:
            return
            
        idx = selected_item.data(Qt.UserRole)
        sorted_history = sorted(self.history_data, key=lambda x: x.get('timestamp', ''), reverse=True)
        selected_item = sorted_history[idx]
        self.transcription_selected.emit(selected_item)
        self.close()
    
    def get_selected_indices(self):
        selected_indices = []
        
        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            checkbox = item.data(Qt.UserRole + 1)
            
            if checkbox.isChecked():
                idx = item.data(Qt.UserRole)
                selected_indices.append(idx)
                
        return selected_indices
    
    def delete_transcription(self):
        selected_indices = self.get_selected_indices()
        
        if not selected_indices:
            return
            
        message = "Are you sure you want to delete the selected item?" if len(selected_indices) == 1 else f"Are you sure you want to delete {len(selected_indices)} selected items?"
        
        reply = QMessageBox.question(
            self, "Confirm Deletion",
            message,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            sorted_history = sorted(self.history_data, key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # Delete items in reverse order to avoid index shifting issues
            for idx in sorted(selected_indices, reverse=True):
                item_to_delete = sorted_history[idx]
                self.history_data.remove(item_to_delete)
                
            self.populate_history_list()
            self.parent().save_history()

# -------------------------- Audio Recorder Thread --------------------------
class AudioRecorder(QThread):
    finished = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.is_recording = False
        self.is_paused = False
        self.output_file = ""
    
    def setup_recording(self, output_file):
        self.output_file = output_file
        self.is_recording = True
        self.is_paused = False
    
    def run(self):
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        CHUNK = 1024
        
        audio = pyaudio.PyAudio()
        stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
        frames = []
        while self.is_recording:
            data = stream.read(CHUNK)
            if not self.is_paused:
                frames.append(data)
            self.msleep(10)
        stream.stop_stream()
        stream.close()
        audio.terminate()
        if frames:
            wf = wave.open(self.output_file, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
            wf.close()
            self.finished.emit(self.output_file)
    
    def stop_recording(self):
        self.is_recording = False
    
    def pause(self):
        self.is_paused = True
    
    def resume(self):
        self.is_paused = False

# ------------------------ Audio Separation Worker Thread ------------------------
class AudioSeparationWorker(QThread):
    finished = pyqtSignal(str)
    log = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, input_file):
        super().__init__()
        self.input_file = input_file
        self.output_file = None
        self.temp_dir = None

    def run(self):
        try:
            self.log.emit("Starting voice separation in background thread...")
            
            # Create a unique output directory
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(tempfile.gettempdir(), f"demucs_output_{timestamp}")
            os.makedirs(output_dir, exist_ok=True)
            self.temp_dir = output_dir
            
            # Prepare the Demucs command
            cmd = [
                "demucs",
                "--two-stems=vocals",   # vocals vs. accompaniment
                "--mp3",                # force MP3 encoding
                "--mp3-bitrate", "320",
                "-o", output_dir,
                self.input_file
            ]
            
            self.log.emit("Running Demucs voice separation...")
            subprocess.run(cmd, check=True)
            
            # Find the vocals file in the output directory
            model_dir = os.path.join(output_dir, os.listdir(output_dir)[0])
            audio_name = os.path.splitext(os.path.basename(self.input_file))[0]
            audio_dir = os.path.join(model_dir, audio_name)
            vocals_file = os.path.join(audio_dir, "vocals.mp3")
            
            if not os.path.exists(vocals_file):
                raise FileNotFoundError(f"Could not find vocals file at {vocals_file}")
            
            # Convert MP3 to WAV for further processing
            vocals_wav = tempfile.mktemp(suffix=".wav")
            audio = AudioSegment.from_mp3(vocals_file)
            audio.export(vocals_wav, format="wav")
            
            self.log.emit("Voice separation completed successfully.")
            self.output_file = vocals_wav
            self.finished.emit(vocals_wav)
            
        except Exception as e:
            self.error.emit(f"Voice separation error: {str(e)}")
            self.finished.emit(self.input_file)  # Return original file on error

    def get_temp_dir(self):
        return self.temp_dir

# ------------------------ Transcription Worker Thread ------------------------
class TranscriptionWorker(QThread):
    finished = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, file_path, model_name="tiny", language=None):
        super().__init__()
        self.file_path = file_path
        self.model_name = model_name
        self.language = language

    def run(self):
        try:
            self.log.emit(f"Loading model: {self.model_name}...")
            model = whisper.load_model(self.model_name)
            self.log.emit("Model loaded. Starting transcription...")
            options = {"language": self.language} if self.language and self.language.lower() != "auto" else {}
            result = model.transcribe(self.file_path, **options)
            self.log.emit("Transcription completed.")
            self.finished.emit(result["text"])
        except Exception as e:
            self.log.emit(f"Error: {str(e)}")
            self.finished.emit("")

# ----------------------------- Main Application Window -----------------------------
class WhisperApp(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ffmpeg_installed = self.check_ffmpeg()
        self.is_recording = False
        self.setup_ui()

        self.player = QMediaPlayer()
        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
        self.player.stateChanged.connect(self.handle_player_state_changed)

        self.selected_file_path = None
        self.available_models = self.get_available_models()
        self.update_model_combo()
        self.setup_history()

        # Initialize timer-related variables
        self.start_time = None
        self.total_paused_time = datetime.timedelta(0)
        self.pause_start = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_recording_time)

    def check_ffmpeg(self):
        """Check if FFmpeg is installed and accessible."""
        return shutil.which("ffmpeg") is not None
    
    def setup_ui(self):
        """Set up the main window UI components."""
        self.setWindowTitle("Whisper - Audio to Text Converter")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        self.setCentralWidget(central_widget)
        
        self.create_menu_bar()
        
        # Settings frame with model and language selection
        settings_frame = QFrame()
        settings_layout = QGridLayout(settings_frame)
        model_label = QLabel("Select Model:")
        self.model_combo = QComboBox()
        settings_layout.addWidget(model_label, 0, 0)
        settings_layout.addWidget(self.model_combo, 0, 1)
        
        self.btn_manage_models = QPushButton("Manage Models")
        self.btn_manage_models.clicked.connect(self.show_model_manager)
        settings_layout.addWidget(self.btn_manage_models, 0, 2)
        
        language_label = QLabel("Select Language:")
        self.language_combo = QComboBox()
        self.language_combo.addItems([
            "Auto", "English", "Polish", "Spanish", "French", "German",
            "Italian", "Russian", "Portuguese", "Japanese", "Chinese",
            "Arabic", "Korean", "Hindi", "Dutch", "Swedish"
        ])
        settings_layout.addWidget(language_label, 1, 0)
        settings_layout.addWidget(self.language_combo, 1, 1)
        
        self.btn_show_folder = QPushButton("Show Models Folder")
        self.btn_show_folder.clicked.connect(self.show_models_folder)
        settings_layout.addWidget(self.btn_show_folder, 1, 2)
        main_layout.addWidget(settings_frame)
        
        # Row for buttons: Choose Audio File, Start Transcription, etc.
        buttons_frame = QFrame()
        buttons_layout = QHBoxLayout(buttons_frame)
        self.btn_choose_file = QPushButton("Choose Audio File")
        self.btn_choose_file.clicked.connect(self.select_file)
        buttons_layout.addWidget(self.btn_choose_file)
        self.btn_start = QPushButton("Start Transcription")
        self.btn_start.clicked.connect(self.start_transcription)
        self.btn_start.setEnabled(False)
        buttons_layout.addWidget(self.btn_start)
        self.btn_open_temp_folder = QPushButton("Open Temp Folder")
        self.btn_open_temp_folder.clicked.connect(self.open_temp_folder)
        self.btn_open_temp_folder.setVisible(True)
        buttons_layout.addWidget(self.btn_open_temp_folder)
        main_layout.addWidget(buttons_frame)
        
        # Combined frame for recording controls and time display
        recording_frame = QFrame()
        recording_layout = QHBoxLayout(recording_frame)

        # Record button
        self.btn_record = QPushButton()
        self.btn_record.setIcon(ThemeManager.get_tinted_icon("assets/icons/mic.svg"))
        self.btn_record.setText("Record Audio")
        self.btn_record.clicked.connect(self.toggle_recording)
        recording_layout.addWidget(self.btn_record)

        # Pause Recording button
        self.btn_pause_record = QPushButton()
        self.btn_pause_record.setIcon(ThemeManager.get_tinted_icon("assets/icons/pause.svg"))
        self.btn_pause_record.setText("Pause Recording")
        self.btn_pause_record.setEnabled(False)
        self.btn_pause_record.clicked.connect(self.toggle_pause_recording)
        recording_layout.addWidget(self.btn_pause_record)

        # Recording time label
        recording_time_label = QLabel("Recording Time:")
        recording_layout.addWidget(recording_time_label)

        # Dynamic time display
        self.time_label = QLabel("00:00:00")
        recording_layout.addWidget(self.time_label)

        # Push everything to the left, leaving empty space on the right
        recording_layout.addStretch()

        # Add the combined frame to the main layout
        main_layout.addWidget(recording_frame)
        
        # File information row: displays the selected file name
        file_info_layout = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        file_info_layout.addWidget(self.file_label)
        file_info_layout.addStretch()
        main_layout.addLayout(file_info_layout)
        
        # Audio processing options group
        self.processing_group = QGroupBox("Audio Processing Options")
        self.processing_group.setCheckable(True)
        self.processing_group.setChecked(False)
        self.processing_group.toggled.connect(self.toggle_processing_options)
        processing_layout = QGridLayout(self.processing_group)
        self.checkbox_noise_reduction = QCheckBox("Noise Reduction")
        self.checkbox_noise_reduction.setToolTip("Reduces ambient noise using spectral gating.")
        processing_layout.addWidget(self.checkbox_noise_reduction, 0, 0)
        self.checkbox_volume_normalization = QCheckBox("Volume Normalization")
        self.checkbox_volume_normalization.setToolTip("Adjusts the volume levels to a target dB value.")
        processing_layout.addWidget(self.checkbox_volume_normalization, 0, 1)
        self.checkbox_bass_boost = QCheckBox("Bass Boost")
        self.checkbox_bass_boost.setToolTip("Enhances the low-frequency components for a richer bass output.")
        processing_layout.addWidget(self.checkbox_bass_boost, 1, 0)
        
        # Add the new Voice Separation checkbox
        self.checkbox_voice_separation = QCheckBox("Voice Separation")
        self.checkbox_voice_separation.setToolTip("Extracts vocals from the audio for clearer transcription.")
        processing_layout.addWidget(self.checkbox_voice_separation, 1, 1)
        
        filters_label = QLabel("Filters:")
        filters_label.setStyleSheet("font-weight: bold;")
        processing_layout.addWidget(filters_label, 2, 0, 1, 2)
        self.checkbox_low_pass = QCheckBox("Low Pass Filter")
        self.checkbox_low_pass.setToolTip("Allows frequencies below the cutoff to pass and attenuates higher frequencies.")
        processing_layout.addWidget(self.checkbox_low_pass, 3, 0)
        self.spinbox_low_pass = QSpinBox()
        self.spinbox_low_pass.setRange(100, 20000)
        self.spinbox_low_pass.setValue(3000)
        self.spinbox_low_pass.setSuffix(" Hz")
        self.spinbox_low_pass.setToolTip("Set the cutoff frequency for the low pass filter.")
        processing_layout.addWidget(self.spinbox_low_pass, 3, 1)
        self.checkbox_high_pass = QCheckBox("High Pass Filter")
        self.checkbox_high_pass.setToolTip("Allows frequencies above the cutoff to pass and attenuates lower frequencies.")
        processing_layout.addWidget(self.checkbox_high_pass, 4, 0)
        self.spinbox_high_pass = QSpinBox()
        self.spinbox_high_pass.setRange(100, 20000)
        self.spinbox_high_pass.setValue(300)
        self.spinbox_high_pass.setSuffix(" Hz")
        self.spinbox_high_pass.setToolTip("Set the cutoff frequency for the high pass filter.")
        processing_layout.addWidget(self.spinbox_high_pass, 4, 1)
        self.checkbox_band_pass = QCheckBox("Band Pass Filter")
        self.checkbox_band_pass.setToolTip("Allows only frequencies within a specific range to pass through.")
        processing_layout.addWidget(self.checkbox_band_pass, 5, 0)
        band_pass_layout = QHBoxLayout()
        self.spinbox_band_low = QSpinBox()
        self.spinbox_band_low.setRange(100, 20000)
        self.spinbox_band_low.setValue(500)
        self.spinbox_band_low.setSuffix(" Hz")
        self.spinbox_band_low.setToolTip("Set the lower cutoff frequency for the band pass filter.")
        band_pass_layout.addWidget(self.spinbox_band_low)
        self.spinbox_band_high = QSpinBox()
        self.spinbox_band_high.setRange(100, 20000)
        self.spinbox_band_high.setValue(4000)
        self.spinbox_band_high.setSuffix(" Hz")
        self.spinbox_band_high.setToolTip("Set the upper cutoff frequency for the band pass filter.")
        band_pass_layout.addWidget(self.spinbox_band_high)
        processing_layout.addLayout(band_pass_layout, 5, 1)
        
        if not self.ffmpeg_installed:
            self.processing_group.hide()
        
        self.toggle_processing_options(False)
        main_layout.addWidget(self.processing_group)
        
        # Audio player frame setup
        self.frame_audio_player = QFrame()
        player_layout = QVBoxLayout(self.frame_audio_player)
        time_layout = QHBoxLayout()
        self.current_time_label = QLabel("0:00")
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.set_position)
        self.duration_label = QLabel("0:00")
        time_layout.addWidget(self.current_time_label)
        time_layout.addWidget(self.position_slider)
        time_layout.addWidget(self.duration_label)
        player_layout.addLayout(time_layout)
        controls_layout = QHBoxLayout()
        self.btn_play = QPushButton()
        self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_play.clicked.connect(self.toggle_playback)
        self.btn_play.setEnabled(False)
        controls_layout.addWidget(self.btn_play)
        self.btn_stop = QPushButton()
        self.btn_stop.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.btn_stop.clicked.connect(self.stop_playback)
        controls_layout.addWidget(self.btn_stop)
        controls_layout.addStretch()
        player_layout.addLayout(controls_layout)
        volume_layout = QHBoxLayout()
        volume_label = QLabel("Volume:")
        volume_layout.addWidget(volume_label)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setToolTip("Adjust volume")
        self.volume_slider.valueChanged.connect(self.set_volume)
        volume_layout.addWidget(self.volume_slider)
        player_layout.addLayout(volume_layout)
        main_layout.addWidget(self.frame_audio_player)
        
        # Logs and transcription result in a splitter
        splitter = QSplitter(Qt.Vertical)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Logs and status messages...")
        result_widget = QWidget()
        result_layout = QVBoxLayout(result_widget)
        result_header = QHBoxLayout()
        result_label = QLabel("Transcription Result:")
        result_label.setStyleSheet("font-weight: bold;")
        result_header.addWidget(result_label)
        result_header.addStretch()
        self.btn_save_text = QPushButton("Save to File .txt")
        self.btn_save_text.clicked.connect(self.save_transcription)
        self.btn_save_text.setEnabled(False)
        result_header.addWidget(self.btn_save_text)
        self.btn_save_audio = QPushButton("Save to File .wav")
        self.btn_save_audio.clicked.connect(self.save_processed_audio)
        self.btn_save_audio.setEnabled(False)
        if not self.ffmpeg_installed:
            self.btn_save_audio.hide()
        result_header.addWidget(self.btn_save_audio)
        result_layout.addLayout(result_header)
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("Transcription result will appear here...")
        result_layout.addWidget(self.result_text)
        splitter.addWidget(self.log_text)
        splitter.addWidget(result_widget)
        splitter.setSizes([150, 350])
        main_layout.addWidget(splitter)
    
    def create_menu_bar(self):
        """Create the menu bar with History and Help menus."""
        menu_bar = self.menuBar()
        history_menu = menu_bar.addMenu("History")
        view_history_action = QAction("View History", self)
        view_history_action.triggered.connect(self.show_history)
        history_menu.addAction(view_history_action)
        clear_history_action = QAction("Clear History", self)
        clear_history_action.triggered.connect(self.clear_history)
        history_menu.addAction(clear_history_action)
        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_app_info)
        help_menu.addAction(about_action)
    
    def setup_history(self):
        """Initialize transcription history from a JSON file in the main assets folder."""
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
        if not os.path.exists(assets_dir):
            os.makedirs(assets_dir)
        self.history_file = os.path.join(assets_dir, "whisper_history.json")
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
            except Exception:
                self.history = []
        else:
            self.history = []
    
    def save_history(self):
        """Save transcription history to a JSON file."""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "History Save Error", f"Could not save history: {str(e)}")
    
    def add_to_history(self, file_path, transcription_text, model, language):
        """Add a new transcription entry to history."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filename = os.path.basename(file_path)
        history_item = {
            "timestamp": timestamp,
            "filename": filename,
            "file_path": file_path,
            "transcription": transcription_text,
            "model": model,
            "language": language
        }
        self.history.append(history_item)
        self.save_history()
    
    def get_available_models(self):
        """Retrieve a list of downloaded models."""
        available_models = []
        cache_dir = os.path.expanduser("~/.cache/whisper")
        if os.path.exists(cache_dir):
            for file in os.listdir(cache_dir):
                if file.endswith(".pt"):
                    model_name = file.split(".")[0]
                    available_models.append(model_name)
        if not available_models:
            available_models = ["tiny"]
        return available_models
    
    def update_model_combo(self):
        """Update the model dropdown with the available models."""
        current_text = self.model_combo.currentText()
        self.model_combo.clear()
        for model in self.available_models:
            self.model_combo.addItem(model)
        if current_text and current_text in self.available_models:
            self.model_combo.setCurrentText(current_text)
    
    def show_app_info(self):
        """Display the Help/Information dialog with usage instructions."""
        about_text = """
        <h2>Whisper Audio to Text Converter</h2>
        <p>This application uses OpenAI's Whisper model to transcribe audio and video files.</p>
        <h3>How to use:</h3>
        <ul>
            <li>Select a model from the dropdown menu (manage models via 'Manage Models').</li>
            <li>Choose an audio or video file ('Choose Audio file').  Video transcription requires FFmpeg.</li>
            <li>Enable 'Audio Processing Options' if desired (FFmpeg is required).</li>
            <li>Click 'Start Transcription'.</li>
            <li>Save results with 'Save to File .txt' or '.wav' (if processed).</li>
            <li>Record audio directly via 'Record Audio' (no time limit).</li>
            <li>View transcription history in the 'History' menu.</li>
        </ul>
        <h3>Notes:</h3>
        <ul>
            <li>FFmpeg is required for video conversion and audio processing.</li>
            <li>When transcribing videos, a temporary .wav file is created.  Remember to delete it if you no longer need it. The filename is randomly generated; the application will inform you of its name and location (Temp folder). Searching by modification date is recommended.</li>
        </ul>
        """
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("About Whisper Audio to Text Converter")
        msg_box.setText(about_text)
        msg_box.setTextFormat(Qt.RichText)
        msg_box.exec_()
    
    def show_model_manager(self):
        """Display the model download/management dialog."""
        dialog = ModelDownloadDialog(self)
        dialog.exec_()
        self.available_models = self.get_available_models()
        self.update_model_combo()
    
    def show_models_folder(self):
        """Open the folder containing downloaded models."""
        cache_dir = os.path.expanduser("~/.cache/whisper")
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        QDesktopServices.openUrl(QUrl.fromLocalFile(cache_dir))
    
    def select_file(self):
        """Open a file dialog for choosing an audio or video file."""
        if self.ffmpeg_installed:
            dialog_title = "Select Audio or Video File"
            file_filter = "Audio/Video Files (*.mp3 *.wav *.flac *.mp4 *.avi *.mov)"
        else:
            dialog_title = "Select Audio File"
            file_filter = "Audio Files (*.mp3 *.wav *.flac)"
        file_path, unused = QFileDialog.getOpenFileName(self, dialog_title, "", file_filter)
        if file_path:
            if file_path.lower().endswith(('.mp4', '.avi', '.mov')) and self.ffmpeg_installed:
                self.log_text.append("Converting video to audio...")
                audio_file = self.convert_video_to_audio(file_path)
                if audio_file:
                    self.selected_file_path = audio_file
                    file_name = os.path.basename(audio_file)
                    self.file_label.setText(f"Selected file: {file_name} (from video)")
                else:
                    QMessageBox.warning(self, "Conversion Error", "Failed to convert video to audio.")
                    return
            else:
                self.selected_file_path = file_path
                file_name = os.path.basename(file_path)
                self.file_label.setText(f"Selected file: {file_name}")
            self.btn_start.setEnabled(True)
            self.setup_audio_player(self.selected_file_path)
            self.log_text.clear()
            self.log_text.append(f"File selected: {self.selected_file_path}")
    
    def convert_video_to_audio(self, video_path):
        """Convert a video file to an audio file using MoviePy."""
        try:
            video = VideoFileClip(video_path)
            audio = video.audio
            # Save the audio file in the same directory as the script instead of temp
            script_dir = os.path.dirname(os.path.abspath(__file__))
            audio_file = os.path.join(script_dir, f"temp_audio_{int(time.time())}.wav")
            audio.write_audiofile(audio_file, codec='pcm_s16le')
            # Store the path so we can clean it up later
            self.temp_audio_file = audio_file
            return audio_file
        except Exception as e:
            self.log_text.append(f"Video conversion error: {e}")
            return None
    
    def setup_audio_player(self, file_path):
        """Configure the audio player with the chosen file."""
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
        self.btn_play.setEnabled(True)
        self.frame_audio_player.setEnabled(True)
    
    def toggle_playback(self):
        """Toggle between play and pause states."""
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()
    
    def stop_playback(self):
        """Stop audio playback."""
        self.player.stop()
    
    def set_position(self, position):
        """Adjust the playback position via the slider."""
        self.player.setPosition(position)
    
    def update_position(self, position):
        """Update the slider and time display during playback."""
        self.position_slider.setValue(position)
        self.current_time_label.setText(self.format_time(position))
    
    def update_duration(self, duration):
        """Set the slider range and duration label."""
        self.position_slider.setRange(0, duration)
        self.duration_label.setText(self.format_time(duration))
    
    def handle_player_state_changed(self, state):
        """Update the play button icon based on media state."""
        if state == QMediaPlayer.PlayingState:
            self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
    
    def set_volume(self, value):
        """Set the volume of the media player."""
        self.player.setVolume(value)
    
    def format_time(self, milliseconds):
        """Format milliseconds into minutes and seconds."""
        seconds = int((milliseconds / 1000) % 60)
        minutes = int((milliseconds / (1000 * 60)) % 60)
        return f"{minutes}:{seconds:02d}"
    
    def toggle_processing_options(self, checked):
        """Enable or disable audio processing options based on group box state."""
        for widget in self.processing_group.findChildren(QWidget):
            if widget != self.processing_group:
                widget.setVisible(checked)
    
    def process_audio(self, input_file):
        """Process the input audio file based on selected options."""
        try:
            audio = AudioSegment.from_file(input_file)
            if self.checkbox_noise_reduction.isChecked():
                self.log_text.append("Applying noise reduction...")
                samples = np.array(audio.get_array_of_samples())
                reduced_samples = nr.reduce_noise(y=samples, sr=audio.frame_rate)
                audio = AudioSegment(
                    reduced_samples.tobytes(),
                    frame_rate=audio.frame_rate,
                    sample_width=audio.sample_width,
                    channels=audio.channels
                )
            if self.checkbox_volume_normalization.isChecked():
                self.log_text.append("Normalizing volume...")
                target_dBFS = -20.0
                change_in_dBFS = target_dBFS - audio.dBFS
                audio = audio.apply_gain(change_in_dBFS)
            if self.checkbox_bass_boost.isChecked():
                self.log_text.append("Applying bass boost...")
                bass = audio.low_pass_filter(150).apply_gain(6)
                audio = audio.overlay(bass)
            if self.checkbox_low_pass.isChecked():
                cutoff = self.spinbox_low_pass.value()
                self.log_text.append(f"Applying low pass filter (cutoff: {cutoff} Hz)...")
                audio = audio.low_pass_filter(cutoff)
            if self.checkbox_high_pass.isChecked():
                cutoff = self.spinbox_high_pass.value()
                self.log_text.append(f"Applying high pass filter (cutoff: {cutoff} Hz)...")
                audio = audio.high_pass_filter(cutoff)
            if self.checkbox_band_pass.isChecked():
                low_band = self.spinbox_band_low.value()
                high_band = self.spinbox_band_high.value()
                if low_band >= high_band:
                    self.log_text.append("Band Pass Filter error: Lower cutoff must be less than upper cutoff.")
                else:
                    self.log_text.append(f"Applying band pass filter (range: {low_band} Hz - {high_band} Hz)...")
                    audio = audio.high_pass_filter(low_band)
                    audio = audio.low_pass_filter(high_band)
            processed_file = tempfile.mktemp(suffix=".wav")
            audio.export(processed_file, format="wav")
            self.log_text.append("Audio processing completed.")
            return processed_file
        except Exception as e:
            self.log_text.append(f"Audio processing error: {e}")
            return input_file
    
    def start_transcription(self):
        """Initiate audio processing and transcription."""
        if not self.selected_file_path:
            QMessageBox.warning(self, "No File", "Please select an audio file first.")
            return
        
        # Disable the start button while processing
        self.btn_start.setEnabled(False)
        self.log_text.append(f"Processing file: {os.path.basename(self.selected_file_path)}")
        
        # Start with the original file
        self.current_processing_file = self.selected_file_path
        
        # Step 1: Apply voice separation if enabled, in a separate thread
        if self.processing_group.isChecked() and self.checkbox_voice_separation.isChecked():
            self.log_text.append("Initiating voice separation...")
            self.separation_worker = AudioSeparationWorker(self.current_processing_file)
            self.separation_worker.log.connect(self.update_log)
            self.separation_worker.error.connect(self.update_log)
            self.separation_worker.finished.connect(self.after_audio_separation)
            self.separation_worker.start()
        else:
            # Skip to audio processing if voice separation is not needed
            self.process_and_transcribe()

    def after_audio_separation(self, separated_file):
        """Handle completion of voice separation and continue with processing."""
        self.current_processing_file = separated_file
        
        # Store the temp directory for cleanup later
        if hasattr(self.separation_worker, 'get_temp_dir'):
            self.voice_separation_temp_dir = self.separation_worker.get_temp_dir()
        
        # Continue with audio processing and transcription
        self.process_and_transcribe()

    def process_and_transcribe(self):
        """Process audio and start transcription after separation (if any)."""
        # Apply audio processing if enabled
        if self.processing_group.isChecked() and self.ffmpeg_installed:
            self.transcription_audio_file = self.process_audio(self.current_processing_file)
            self.processing_applied = True
        else:
            self.transcription_audio_file = self.current_processing_file
            self.processing_applied = False
        
        # Start transcription
        selected_model = self.model_combo.currentText()
        selected_language = self.language_combo.currentText()
        language = None if selected_language.lower() == "auto" else selected_language
        
        self.log_text.append(f"Starting transcription for file: {os.path.basename(self.transcription_audio_file)}")
        self.worker = TranscriptionWorker(self.transcription_audio_file, selected_model, language)
        self.worker.log.connect(self.update_log)
        self.worker.finished.connect(self.transcription_finished)
        self.worker.start()
    
    def update_log(self, message):
        """Append log messages to the log text area."""
        self.log_text.append(message)
    
    def transcription_finished(self, result_text):
        """Handle transcription completion."""
        try:
            # Clean up temporary audio file if it exists (in script directory)
            if hasattr(self, 'temp_audio_file') and os.path.exists(self.temp_audio_file):
                os.remove(self.temp_audio_file)
                delattr(self, 'temp_audio_file')
                self.log_text.append("Cleaned up temporary audio file.")
                
            # Clean up temporary vocals WAV file if it exists (in script directory)
            if hasattr(self, 'vocals_wav_file') and os.path.exists(self.vocals_wav_file):
                os.remove(self.vocals_wav_file)
                delattr(self, 'vocals_wav_file')
                self.log_text.append("Cleaned up temporary vocals WAV file.")
                
            # Inform user about files in temp folder that need manual cleanup
            # but don't try to delete them
            self.log_text.append("IMPORTANT: Temporary files in system temp folder need to be manually deleted.")
            
            # Inform specifically about Demucs output if available
            if hasattr(self, 'demucs_output_directory'):
                self.log_text.append(f"Please use the 'Open Temp Folder' button and delete the directory: {self.demucs_output_directory}")
                delattr(self, 'demucs_output_directory')
                
            # Also mention potential files from process_audio
            self.log_text.append("Also check for any temporary WAV files in the temp folder from audio processing.")
            
        except Exception as e:
            self.log_text.append(f"Error cleaning up temporary files: {str(e)}")
        
        if result_text:
            self.result_text.setPlainText(result_text)
            self.btn_save_text.setEnabled(True)
            if self.processing_applied and self.ffmpeg_installed:
                self.btn_save_audio.setEnabled(True)
            model = self.model_combo.currentText()
            language = self.language_combo.currentText()
            self.add_to_history(self.selected_file_path, result_text, model, language)
        else:
            self.result_text.setPlainText("Transcription failed.")
        
        # Re-enable the start button
        self.btn_start.setEnabled(True)
    
    def save_transcription(self):
        """Save the transcription output to a text file."""
        file_path, unused = QFileDialog.getSaveFileName(self, "Save Transcription", "", "Text Files (*.txt)")
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.result_text.toPlainText())
            QMessageBox.information(self, "Success", "Transcription saved successfully.")
    
    def save_processed_audio(self):
        """Save the processed audio file."""
        if not hasattr(self, 'transcription_audio_file') or not self.transcription_audio_file:
            QMessageBox.warning(self, "No Audio", "No audio file to save.")
            return
        file_path, unused = QFileDialog.getSaveFileName(self, "Save Audio File", "", "WAV Files (*.wav)")
        if file_path:
            try:
                shutil.copy(self.transcription_audio_file, file_path)
                QMessageBox.information(self, "Success", "Audio file saved successfully.")
            except Exception as e:
                QMessageBox.warning(self, "Save Error", f"Could not save audio file: {str(e)}")
    
    def toggle_recording(self):
        """Start or stop microphone recording and manage the timer."""
        if not self.is_recording:
            self.is_recording = True
            self.btn_record.setText("Stop Recording")
            self.btn_record.setIcon(ThemeManager.get_tinted_icon("assets/icons/stop-circle.svg"))
            self.btn_pause_record.setEnabled(True)
            self.recording_file = tempfile.mktemp(suffix='.wav')
            self.recorder = AudioRecorder()
            self.recorder.setup_recording(self.recording_file)
            self.recorder.finished.connect(self.recording_finished)
            self.recorder.start()
            # Start the recording timer
            self.start_time = datetime.datetime.now()
            self.total_paused_time = datetime.timedelta(0)
            self.pause_start = None
            self.timer.start(1000)  # Update every second
        else:
            self.is_recording = False
            self.btn_record.setText("Record Audio")
            self.btn_record.setIcon(ThemeManager.get_tinted_icon("assets/icons/mic.svg"))
            self.btn_pause_record.setEnabled(False)
            self.recorder.stop_recording()
            # Stop the timer and reset the label
            self.timer.stop()
            self.time_label.setText("00:00:00")
    
    def toggle_pause_recording(self):
        """Pause or resume recording and update pause timing."""
        if self.recorder.is_paused:
            # Resuming recording
            if self.pause_start:
                self.total_paused_time += datetime.datetime.now() - self.pause_start
            self.pause_start = None
            self.recorder.resume()
            self.btn_pause_record.setText("Pause Recording")
            self.btn_pause_record.setIcon(ThemeManager.get_tinted_icon("assets/icons/pause.svg"))
            self.log_text.append("Recording resumed.")
        else:
            # Pausing recording
            self.pause_start = datetime.datetime.now()
            self.recorder.pause()
            self.btn_pause_record.setText("Resume Recording")
            self.btn_pause_record.setIcon(ThemeManager.get_tinted_icon("assets/icons/play.svg"))  # Assuming you have a play icon
            self.log_text.append("Recording paused.")
    
    def update_recording_time(self):
        """Update the recording time display."""
        if self.is_recording:
            if self.recorder.is_paused and self.pause_start:
                # Show time up to the pause point
                delta = self.pause_start - self.start_time - self.total_paused_time
            else:
                # Show current elapsed time excluding paused periods
                delta = datetime.datetime.now() - self.start_time - self.total_paused_time
            self.time_label.setText(str(delta).split('.')[0])  # Display in HH:MM:SS format
    
    def recording_finished(self, file_path):
        """Handle actions once recording has finished."""
        self.selected_file_path = file_path
        self.file_label.setText("Recorded audio")
        self.btn_start.setEnabled(True)
        self.setup_audio_player(file_path)
    
    def open_temp_folder(self):
        """Open the temporary folder where recordings are stored."""
        temp_dir = tempfile.gettempdir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(temp_dir))
    
    def show_history(self):
        """Display the transcription history dialog."""
        if not self.history:
            QMessageBox.information(self, "No History", "No transcription history available.")
            return
        dialog = TranscriptionHistoryDialog(self.history, self)
        dialog.transcription_selected.connect(self.load_from_history)
        dialog.exec_()
    
    def load_from_history(self, history_item):
        """Load a transcription from history."""
        file_path = history_item.get('file_path', '')
        if os.path.exists(file_path):
            self.selected_file_path = file_path
            self.file_label.setText(f"Selected file: {os.path.basename(file_path)}")
            self.btn_start.setEnabled(True)
            self.setup_audio_player(file_path)
        self.result_text.setPlainText(history_item.get('transcription', ''))
        self.btn_save_text.setEnabled(True)
    
    def clear_history(self):
        """Clear all transcription history."""
        if self.history:
            self.history = []
            self.save_history()
            QMessageBox.information(self, "History Cleared", "Transcription history has been cleared.")
            
    def separate_audio(self, input_file):
        """Separate vocals from the input audio file using Demucs."""
        try:
            self.log_text.append("Starting voice separation...")
            
            # Create a unique timestamp for this separation
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # This is the directory where Demucs will actually save files
            demucs_temp_dir = os.path.join(tempfile.gettempdir(), f"demucs_output_{timestamp}")
            
            # Prepare the Demucs command with MP3 output
            cmd = [
                "demucs",
                "--two-stems=vocals",   # vocals vs. accompaniment
                "--mp3",                # force MP3 encoding to avoid backend errors
                "--mp3-bitrate", "320",
                "-o", demucs_temp_dir,  # output directory
                input_file
            ]
            
            self.log_text.append("Running Demucs voice separation...")
            process = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Track the actual directory used by Demucs
            actual_output_dir = None
            if process.stdout:
                for line in process.stdout.splitlines():
                    if "Separated tracks will be stored in" in line:
                        actual_output_dir = line.split("Separated tracks will be stored in ")[1].strip()
                        break
            
            # If we couldn't get it from stdout, try stderr
            if not actual_output_dir and process.stderr:
                for line in process.stderr.splitlines():
                    if "Separated tracks will be stored in" in line:
                        actual_output_dir = line.split("Separated tracks will be stored in ")[1].strip()
                        break
            
            # If we still don't have it, use our best guess
            if not actual_output_dir:
                actual_output_dir = demucs_temp_dir
                self.log_text.append(f"Could not detect Demucs output directory, using: {actual_output_dir}")
            else:
                self.log_text.append(f"Demucs output directory: {actual_output_dir}")
            
            # Store the directory path to inform the user later
            self.demucs_output_directory = actual_output_dir
            
            # Find the vocals file in the output directory
            model_name = "htdemucs"  # Default model name
            audio_name = os.path.splitext(os.path.basename(input_file))[0]
            audio_dir = os.path.join(actual_output_dir, model_name, audio_name)
            vocals_file = os.path.join(audio_dir, "vocals.mp3")
            
            if not os.path.exists(vocals_file):
                # Try looking through all directories to find the vocals file
                possible_models = os.listdir(actual_output_dir) if os.path.exists(actual_output_dir) else []
                for model in possible_models:
                    possible_path = os.path.join(actual_output_dir, model, audio_name, "vocals.mp3")
                    if os.path.exists(possible_path):
                        vocals_file = possible_path
                        self.log_text.append(f"Found vocals file at: {vocals_file}")
                        break
                else:
                    raise FileNotFoundError(f"Could not find vocals file in {actual_output_dir}")
            
            # Convert MP3 to WAV for further processing if needed
            script_dir = os.path.dirname(os.path.abspath(__file__))
            vocals_wav = os.path.join(script_dir, f"vocals_{timestamp}.wav")
            audio = AudioSegment.from_mp3(vocals_file)
            audio.export(vocals_wav, format="wav")
            
            self.log_text.append("Voice separation completed successfully.")
            
            # Store the vocals file path to clean up later
            self.vocals_wav_file = vocals_wav
            
            return vocals_wav
        except Exception as e:
            self.log_text.append(f"Voice separation error: {str(e)}")
            import traceback
            self.log_text.append(traceback.format_exc())
            return input_file
    
    def closeEvent(self, event):
        """Handle application close event."""
        if self.is_recording:
            self.recorder.stop_recording()
            self.recorder.wait()
        super().closeEvent(event)

# ---------------------------- Main Entry Point ----------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WhisperApp()
    window.show()
    sys.exit(app.exec_())