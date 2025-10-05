## file: audio_utils.py
import datetime
import pyaudio
import wave
import whisper
from PyQt5.QtCore import QThread, pyqtSignal

class AudioRecorder(QThread):
    finished = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.is_recording = False
        self.is_paused = False
        self.output_file = ""
        self.start_time = None

    def setup_recording(self, output_file):
        self.output_file = output_file
        self.is_recording = True
        self.is_paused = False
        self.start_time = datetime.datetime.now()

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

class TranscriptionWorker(QThread):
    finished = pyqtSignal(str)
    
    def __init__(self, file_path, model_name="tiny", language=None):
        super().__init__()
        self.file_path = file_path
        self.model_name = model_name
        self.language = language

    def run(self):
        try:
            model = whisper.load_model(self.model_name)
            result = model.transcribe(self.file_path, language=self.language)
            self.finished.emit(result["text"])
        except Exception as e:
            self.finished.emit(f"Error: {str(e)}")
