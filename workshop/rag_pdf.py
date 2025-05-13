import sys
import os
import io
import logging
import json
import re
import math
import base64
import time
import datetime
from pathlib import Path
from typing import Any, List, Dict, Optional, Tuple, Union
from dataclasses import dataclass
from difflib import SequenceMatcher
from PIL import Image
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from settings.llm_api_aggregator import WWSettingsManager
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.messages.base import BaseMessage

import fitz  # PyMuPDF
import pymupdf4llm
import tiktoken
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QPoint
from PyQt5.QtGui import QTextOption, QKeySequence, QPixmap, QCursor, QTextDocument, QTextCursor, QImage
from PyQt5.QtWidgets import (QTabWidget, QWidget, QVBoxLayout, QGroupBox, QHBoxLayout, 
                            QLineEdit, QPushButton, QTextEdit, QSpinBox, QPlainTextEdit, 
                            QLabel, QProgressBar, QScrollArea, QFileDialog, QMessageBox, 
                            QGridLayout, QSplitter, QComboBox, QDoubleSpinBox, QDialog,
                            QListWidgetItem, QMenuBar, QAction, QListWidget, QStatusBar,
                            QMenu, QInputDialog, QShortcut, QApplication, QCheckBox,
                            QSizePolicy, QStackedWidget)
from settings.llm_api_aggregator import WWApiAggregator
from util.find_dialog import FindDialog

# Setup logging
logging.basicConfig(
    filename='pdf_rag_app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('PdfRagApp')

# Define settings data structure
@dataclass
class AppSettings:
    last_pdf_path_manual: str = ""
    last_pdf_path_qa: str = ""
    last_from_page_manual: int = 0
    last_to_page_manual: int = 0
    last_chunk_size: int = 20000
    default_prompt: str = ""
    
class VisionMessage(HumanMessage):
    """Custom Message class for vision-based LLMs"""
    def __init__(self, content: Union[str, List[Dict[str, Any]]]):
        super().__init__(content=content)

# Utility class for token counting
class TokenCounter:
    @staticmethod
    def count_tokens(text: str, encoding_name: str = 'cl100k_base') -> int:
        encoder = tiktoken.get_encoding(encoding_name)
        return len(encoder.encode(text))

    @staticmethod
    def get_encoder(encoding_name: str = 'cl100k_base'):
        return tiktoken.get_encoding(encoding_name)

# PDF processing utilities
class PdfProcessor:
    # Abbreviations to consider when splitting sentences
    ABBREVIATIONS = {'np', 'dr', 'mgr', 'itp', 'e.g', 'i.e', 'etc'}
    # Split sentences on punctuation followed by whitespace
    SENTENCE_SPLIT_REGEX = re.compile(r'(?<=[\.\!\?])\s+')
    # Detect Markdown structures: headers, code blocks, tables
    STRUCTURE_REGEX = re.compile(r'^(#{1,6}\s+|```|\|)', re.MULTILINE)
    # Paragraph split: two or more consecutive newlines
    PARAGRAPH_SPLIT_REGEX = re.compile(r'\n{2,}')

    @staticmethod
    def load_document(pdf_path: str) -> Tuple[int, Optional[str]]:
        try:
            doc = fitz.open(pdf_path)
            page_count = doc.page_count
            doc.close()
            return page_count, None
        except Exception as e:
            logger.error(f"Error loading PDF: {e}")
            return 0, f"Error loading PDF: {e}"

    @staticmethod
    def convert_to_markdown(pdf_path: str, pages: List[int]) -> Tuple[str, Optional[str]]:
        try:
            markdown_text = pymupdf4llm.to_markdown(pdf_path, pages=pages)
            if not markdown_text.strip():
                return "", "No extractable text in PDF."
            return markdown_text, None
        except Exception as e:
            logger.error(f"Error converting PDF: {e}")
            return "", f"Error converting PDF: {e}"

    @staticmethod
    def preprocess(text: str) -> str:
        # Remove hyphenation at line breaks (e.g., "ex-\nample" -> "example")
        return re.sub(r'-\n\s*', '', text)

    @classmethod
    def split_paragraphs(cls, text: str) -> List[str]:
        # Split on two or more newlines OR at sentence boundaries
        parts = re.split(r'\n{2,}|\.(?=\s+[A-Z])|(?<=[.!?])\s+(?=[A-Z])', text)
        paragraphs: List[str] = []
        current_paragraph = ""

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if current_paragraph and not current_paragraph[-1].isalpha():
                current_paragraph += " " + part
            else:
                if paragraphs and paragraphs[-1] == "":
                    paragraphs.pop()
                paragraphs.append(current_paragraph)
                current_paragraph = part

        if current_paragraph:
            paragraphs.append(current_paragraph)

        return paragraphs

    @classmethod
    def is_structural(cls, text: str) -> bool:
        # Structural if any line starts with markdown structural element
        for line in text.splitlines():
            if cls.STRUCTURE_REGEX.match(line):
                return True
        return False

    @classmethod
    def split_sentences(cls, text: str) -> List[str]:
        parts = cls.SENTENCE_SPLIT_REGEX.split(text)
        sentences: List[str] = []
        i = 0
        while i < len(parts):
            segment = parts[i]
            lower = segment.strip().lower()
            # If segment ends with an abbreviation, merge with the next part
            if any(lower.endswith(abbr + '.') for abbr in cls.ABBREVIATIONS) and i + 1 < len(parts):
                segment = segment + ' ' + parts[i + 1]
                i += 2
            else:
                i += 1
            sentences.append(segment.strip())
        return sentences

    @staticmethod
    def chunk_text_intelligently(text: str, max_tokens: int) -> List[str]:
        encoder = TokenCounter.get_encoder()
        text = PdfProcessor.preprocess(text)

        # If entire text fits in one chunk, return it as-is
        total_tokens = TokenCounter.count_tokens(text)
        if total_tokens <= max_tokens:
            return [text]

        desired_chunks = math.ceil(total_tokens / max_tokens)
        paragraphs = PdfProcessor.split_paragraphs(text)
        chunks: List[str] = []
        current = ''
        current_tokens = 0

        def flush_current():
            nonlocal current, current_tokens
            if current:
                chunks.append(current)
                current = ''
                current_tokens = 0

        for para in paragraphs:
            if PdfProcessor.is_structural(para):
                flush_current()
                chunks.append(para)
                continue

            para_tokens = TokenCounter.count_tokens(para)
            # Try to add paragraph to current chunk
            if current_tokens + para_tokens <= max_tokens:
                if current:
                    current += '\n\n' + para
                    current_tokens += para_tokens + 2
                else:
                    current = para
                    current_tokens = para_tokens
            else:
                # Paragraph too big or would overflow current chunk
                flush_current()
                if para_tokens <= max_tokens:
                    current = para
                    current_tokens = para_tokens
                else:
                    for sent in PdfProcessor.split_sentences(para):
                        sent_tokens = TokenCounter.count_tokens(sent)
                        if sent_tokens > max_tokens:
                            chunks.append(sent)
                        elif current_tokens + sent_tokens <= max_tokens:
                            if current:
                                current += ' ' + sent
                                current_tokens += sent_tokens + 1
                            else:
                                current = sent
                                current_tokens = sent_tokens
                        else:
                            flush_current()
                            current = sent
                            current_tokens = sent_tokens
        flush_current()

        # Merge small chunks to minimize count up to desired_chunks
        i = 0
        while len(chunks) > desired_chunks and i < len(chunks) - 1:
            tokens_i = TokenCounter.count_tokens(chunks[i])
            tokens_j = TokenCounter.count_tokens(chunks[i+1])
            if tokens_i + tokens_j <= max_tokens:
                # merge
                chunks[i] = chunks[i] + '\n\n' + chunks[i+1]
                del chunks[i+1]
                # restart from previous index
                i = max(i-1, 0)
            else:
                i += 1

        return chunks

# Enhanced PDF processing for QA
class EnhancedPdfProcessor:
    @staticmethod
    def semantic_with_boost(
        full_text: str,
        question: str,
        min_semantic: float = 0.2,
        top_k: int = 5,
        window: int = 1
    ) -> List[Dict]:
        """
        Perform semantic similarity search with keyword-based boost.
        Returns up to top_k paragraphs plus surrounding context.
        """
        # clean and split
        query_clean = question.lower().strip()
        words = [w.strip('.,?!') for w in query_clean.split() if w]
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', full_text) if p.strip()]
        results = []

        # compute scores per paragraph
        for idx, para in enumerate(paragraphs):
            para_lower = para.lower()
            sim = SequenceMatcher(None, query_clean, para_lower).ratio()
            kw_hits = sum(bool(re.search(rf'\b{re.escape(w)}\b', para_lower)) for w in words)
            score = 0.7 * sim + 0.3 * (kw_hits / max(1, len(words)))
            if score >= min_semantic:
                results.append({
                    "paragraph_id": idx,
                    "text": para,
                    "match_type": "semantic+boost",
                    "score": round(score, 2),
                    "keyword_hits": kw_hits
                })

        # sort and cut to top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:top_k]

        # attach context
        for hit in results:
            idx = hit["paragraph_id"]
            start = max(0, idx - window)
            end   = min(len(paragraphs) - 1, idx + window)
            hit["context"] = "\n\n".join(paragraphs[start:end+1])

        return results

    @staticmethod
    def semantic_only(
        full_text: str,
        question: str,
        min_similarity: float = 0.2,
        top_k: int = 5,
        window: int = 1
    ) -> List[Dict]:
        """
        Perform pure semantic similarity search.
        Returns up to top_k paragraphs plus surrounding context.
        """
        query_clean = question.lower().strip()
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', full_text) if p.strip()]
        results = []

        for idx, para in enumerate(paragraphs):
            sim = SequenceMatcher(None, query_clean, para.lower()).ratio()
            if sim >= min_similarity:
                results.append({
                    "paragraph_id": idx,
                    "text": para,
                    "match_type": "semantic",
                    "score": round(sim, 2)
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:top_k]

        for hit in results:
            idx = hit["paragraph_id"]
            start = max(0, idx - window)
            end   = min(len(paragraphs) - 1, idx + window)
            hit["context"] = "\n\n".join(paragraphs[start:end+1])

        return results

    @staticmethod
    def keyword_only(
        full_text: str,
        question: str,
        top_k: int = 5,
        window: int = 1
    ) -> List[Dict]:
        """
        Perform exact keyword search. Treats every word in the question as keyword.
        Returns up to top_k paragraphs plus surrounding context.
        """
        query_clean = question.lower().strip()
        words = [w.strip('.,?!') for w in query_clean.split() if w]
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', full_text) if p.strip()]
        results = []

        for idx, para in enumerate(paragraphs):
            para_lower = para.lower()
            kw_hits = sum(1 for w in words if re.search(rf'\b{re.escape(w)}\b', para_lower))
            if kw_hits > 0:
                score = round(kw_hits / len(words), 2)
                results.append({
                    "paragraph_id": idx,
                    "text": para,
                    "match_type": "keyword",
                    "score": score,
                    "keyword_hits": kw_hits
                })

        results.sort(key=lambda x: (x["keyword_hits"], x["score"]), reverse=True)
        results = results[:top_k]

        for hit in results:
            idx = hit["paragraph_id"]
            start = max(0, idx - window)
            end   = min(len(paragraphs) - 1, idx + window)
            hit["context"] = "\n\n".join(paragraphs[start:end+1])

        return results

# Simple QA system
class SimpleQaSystem:
    @staticmethod
    def generate_answer(
        question: str,
        context: List[Dict],
        max_context_tokens: int = 4000,
        extra_instructions: str = ""
    ) -> str:
        """
        Generate an answer based ONLY on the provided context.
        If extra_instructions is non-empty, prepend them before sending the prompt,
        and omit the standard Rules section entirely.
        """
        if not context:
            return "No relevant information found in the document."

        # Build context string up to the token limit
        encoder = TokenCounter.get_encoder()
        context_str = ""
        total_tokens = 0

        for entry in context:
            entry_tokens = TokenCounter.count_tokens(entry["text"])
            if total_tokens + entry_tokens > max_context_tokens:
                break
            context_str += f"\n\n[Paragraph {entry['paragraph_id']}] {entry['text']}"
            total_tokens += entry_tokens

        # Prepare prompt sections
        prompt_sections = [
            f"**Question:**\n{question}",
            f"**Context:**{context_str}"
        ]

        # If user provided extra instructions, add them and skip Rules
        if extra_instructions:
            prompt_sections.append(
                "**User Instructions (priority):**\n"
                f"{extra_instructions}"
            )
        else:
            # Only include the default Rules when no extra instructions are given
            prompt_sections.append(
                "**Rules:**\n"
                "1. Be precise.\n"
                "2. If unsure, say “I don’t know.”\n"
                "3. Mention relevant paragraph numbers."
            )

        # Join all parts into the final prompt
        prompt = "\n\n".join(prompt_sections)

        response, _ = LlmClient.send_prompt(prompt)
        return response

# LLM client
class LlmClient:
    @staticmethod
    def send_prompt(full_prompt: str) -> Tuple[str, Optional[str]]:
        """
        Send a single string (which can include embedded Base64 image)
        to the LLM API.
        """
        try:
            response = WWApiAggregator.send_prompt_to_llm(full_prompt)
            return response, None
        except Exception as e:
            logger.error(f"Error calling LLM API: {e}")
            return "", f"Error calling LLM API: {e}"

    @staticmethod
    def send_prompt_with_image(prompt: str, image_bytes: bytes) -> tuple[str, Optional[str]]:
        """
        Send prompt with image to LLM using provider-specific format
        """
        try:
            # Get the current provider name
            provider_name = WWSettingsManager.get_active_llm_name()
            
            # Encode image to base64
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            if provider_name == "LMStudio" or provider_name == "OpenAI":
                # OpenAI format (works with LM Studio)
                vision_content = [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
                
                # Create conversation history for OpenAI format
                conversation_history = [
                    {
                        "role": "user",
                        "content": vision_content
                    }
                ]
                
                response = WWApiAggregator.send_prompt_to_llm(
                    final_prompt="",
                    conversation_history=conversation_history
                )
                
            elif provider_name == "Anthropic":
                # Claude format
                final_prompt = (
                    prompt +
                    "\n\n<image>\n" +
                    base64_image +
                    "\n</image>"
                )
                
                response = WWApiAggregator.send_prompt_to_llm(final_prompt)
                
            elif provider_name == "Google":
                # Google Gemini format
                vision_content = [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url", 
                        "image_url": f"data:image/jpeg;base64,{base64_image}"
                    }
                ]
                
                conversation_history = [
                    {
                        "role": "user",
                        "content": vision_content
                    }
                ]
                
                response = WWApiAggregator.send_prompt_to_llm(
                    final_prompt="",
                    conversation_history=conversation_history
                )
                
            elif provider_name == "Ollama":
                # Ollama uses markdown format for images
                final_prompt = f"{prompt}\n\n![image](data:image/jpeg;base64,{base64_image})"
                response = WWApiAggregator.send_prompt_to_llm(final_prompt)
                
            else:
                # Dla innych providerów - uproszczone podejście z formatem markdown
                # Wiele modeli rozumie ten format
                final_prompt = f"{prompt}\n\n![Image](data:image/jpeg;base64,{base64_image})"
                response = WWApiAggregator.send_prompt_to_llm(final_prompt)
            
            return response, None
            
        except Exception as e:
            import logging
            import traceback
            logging.error(f"Error sending image to LLM: {e}")
            logging.error(traceback.format_exc())  # Pełny stack trace
            return "", f"Error calling LLM API: {e}"


# Worker for PDF processing
class PdfProcessingWorker(QThread):
    finished = pyqtSignal(str, list, str)
    progress = pyqtSignal(int)
    
    def __init__(self, pdf_path: str, pages: List[int], max_tokens: int = None):
        super().__init__()
        self.pdf_path = pdf_path
        self.pages = pages
        self.max_tokens = max_tokens
    
    def run(self):
        # Process PDF in a separate thread
        markdown, error = PdfProcessor.convert_to_markdown(self.pdf_path, self.pages)
        if error:
            self.finished.emit("", [], error)
            return
        if self.max_tokens:
            chunks = PdfProcessor.chunk_text_intelligently(markdown, self.max_tokens)
        else:
            chunks = []
        self.finished.emit(markdown, chunks, "")

# Worker for LLM processing
class LlmWorker(QThread):
    result_ready = pyqtSignal(int, str, str)
    
    def __init__(self, chunk_idx: int, prompt: str, chunk_text: str):
        super().__init__()
        self.chunk_idx = chunk_idx
        self.prompt = prompt
        self.chunk_text = chunk_text
    
    def run(self):
        # Send chunk to LLM in a separate thread
        full_input = f"{self.prompt}\n\n{self.chunk_text}"
        try:
            response = WWApiAggregator.send_prompt_to_llm(full_input)
            self.result_ready.emit(self.chunk_idx, response, "")
        except Exception as e:
            self.result_ready.emit(self.chunk_idx, "", f"Error: {str(e)}")
            
class QaWorker(QThread):
    finished = pyqtSignal(str, list)  # result_text, relevant_sections
    error = pyqtSignal(str)

    def __init__(self, markdown_text, question, mode,
                 min_sim, top_k, context_mode,
                 custom_instr, snippet_length):
        super().__init__()
        self.markdown_text   = markdown_text
        self.question        = question
        self.mode            = mode
        self.min_sim         = min_sim
        self.top_k           = top_k
        self.context_mode    = context_mode
        self.custom_instr    = custom_instr
        self.snippet_length  = snippet_length

    def run(self):
        try:
            # Determine window and snippet mode based on context_mode
            cm = self.context_mode
            if cm.startswith("Snippet"):
                snippet_mode = True
                window = 0
            elif "Surrounding" in cm:
                snippet_mode = False
                try:
                    # e.g. "Full Paragraph + Surrounding 2 paragraphs"
                    window = int(cm.split()[-2])
                except (ValueError, IndexError):
                    window = 1
            elif cm.startswith("Full Paragraph"):
                snippet_mode = False
                window = 0
            else:
                snippet_mode = False
                window = 0

            # Retrieve relevant sections with context window
            if "Boost" in self.mode:
                relevant_sections = EnhancedPdfProcessor.semantic_with_boost(
                    full_text=self.markdown_text,
                    question=self.question,
                    min_semantic=self.min_sim,
                    top_k=self.top_k,
                    window=window
                )
            elif "Semantic" in self.mode:
                relevant_sections = EnhancedPdfProcessor.semantic_only(
                    full_text=self.markdown_text,
                    question=self.question,
                    min_similarity=self.min_sim,
                    top_k=self.top_k,
                    window=window
                )
            else:
                relevant_sections = EnhancedPdfProcessor.keyword_only(
                    full_text=self.markdown_text,
                    question=self.question,
                    top_k=self.top_k,
                    window=window
                )

            # Prepare context for the LLM
            if snippet_mode:
                llm_context = [
                    {
                        "paragraph_id": s["paragraph_id"],
                        "text": s["text"][:self.snippet_length],
                        "score": s.get("score", 1.0)
                    }
                    for s in relevant_sections
                ]
            else:
                llm_context = relevant_sections

            # Generate the answer via LLM
            answer = SimpleQaSystem.generate_answer(
                question=self.question,
                context=llm_context,
                extra_instructions=self.custom_instr
            )

            # Build the result text for UI
            result_text  = f"Question: {self.question}\n\n"
            result_text += f"Answer:\n{answer}\n\n"
            result_text += "Relevant paragraphs:\n"
            for sec in relevant_sections:
                result_text += (
                    f"\nParagraph {sec['paragraph_id']} "
                    f"(score: {sec.get('score', 1.0):.2f}):\n"
                    f"{sec['text']}\n"
                )

            # Emit finished signal
            self.finished.emit(result_text, relevant_sections)

        except Exception as e:
            # Emit error signal
            self.error.emit(f"Error: {str(e)}")

class ProcessingThread(QThread):
    progress_updated = pyqtSignal(int, str)
    task_completed = pyqtSignal(int, str)
    all_completed = pyqtSignal()
    
    def __init__(self, parent, tasks):
        super().__init__(parent)
        self.parent = parent
        self.tasks = tasks
        
    def run(self):
        total_tasks = len(self.tasks)
        
        for i, task in enumerate(self.tasks):
            # Check if processing was cancelled
            if self.parent.processing_cancelled:
                self.progress_updated.emit(100, "Cancelled")
                break
            
            # Update progress
            progress = int((i / total_tasks) * 100)
            self.progress_updated.emit(progress, f"Processing {i+1}/{total_tasks}: {task['item']['name']}")
            
            try:
                # Get the image data
                idx = task['index']
                item = task['item']
                prompt = task['prompt']
                
                # Process the image
                img_bytes = self.prepare_image(item)
                
                # Send to LLM
                response, err = LlmClient.send_prompt_with_image(prompt, img_bytes)
                
                if err:
                    response = f"Error: {err}"
                
                # Emit result
                self.task_completed.emit(idx, response)
                
            except Exception as e:
                # Handle any exceptions
                self.task_completed.emit(task['index'], f"Error: {str(e)}")
            
            # Small delay to prevent UI freezing and allow for cancellation
            time.sleep(0.1)
        
        # Signal completion
        if not self.parent.processing_cancelled:
            self.progress_updated.emit(100, "Completed")
        self.all_completed.emit()
    
    def prepare_image(self, item):
        # Get custom resolution settings from parent
        max_width = self.parent.sb_max_width.value()
        max_height = self.parent.sb_max_height.value()
        quality = self.parent.sb_quality.value()
        
        pil_img = None
        
        if item['type'] == 'pdf_page':
            # Render the PDF page
            page = item['doc'][item['page_num']]
            pix = page.get_pixmap(dpi=300)
            pil_img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            
        elif item['type'] == 'image':
            # Load the image file
            pil_img = Image.open(item['path'])
            
            # Convert to RGB if needed
            if pil_img.mode != 'RGB':
                pil_img = pil_img.convert('RGB')
        
        # Resize to maintain aspect ratio within max dimensions
        original_width, original_height = pil_img.size
        width_ratio = max_width / original_width
        height_ratio = max_height / original_height
        scale_ratio = min(width_ratio, height_ratio)
        
        # Only scale down, not up
        if scale_ratio < 1.0:
            new_width = int(original_width * scale_ratio)
            new_height = int(original_height * scale_ratio)
            pil_img = pil_img.resize((new_width, new_height), Image.LANCZOS)
        
        # Compress to JPEG
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()

# Settings manager
class SettingsManager:
    SETTINGS_FILE = "pdf_rag_settings.json"
    
    @staticmethod
    def load_settings() -> AppSettings:
        # Load settings from file
        try:
            if os.path.exists(SettingsManager.SETTINGS_FILE):
                with open(SettingsManager.SETTINGS_FILE, 'r') as f:
                    data = json.load(f)
                    return AppSettings(
                        last_pdf_path_manual=data.get('last_pdf_path_manual', ""),
                        last_pdf_path_qa=data.get('last_pdf_path_qa', ""),
                        last_from_page_manual=data.get('last_from_page_manual', 0),
                        last_to_page_manual=data.get('last_to_page_manual', 0),
                        last_chunk_size=data.get('last_chunk_size', 20000),
                        default_prompt=data.get('default_prompt', "")
                    )
        except Exception as e:
            logger.error(f"Error loading settings: {str(e)}")
        return AppSettings()
    
    @staticmethod
    def save_settings(settings: AppSettings) -> None:
        # Save settings to file
        try:
            with open(SettingsManager.SETTINGS_FILE, 'w') as f:
                json.dump({
                    'last_pdf_path_manual': settings.last_pdf_path_manual,
                    'last_pdf_path_qa': settings.last_pdf_path_qa,
                    'last_from_page_manual': settings.last_from_page_manual,
                    'last_to_page_manual': settings.last_to_page_manual,
                    'last_chunk_size': settings.last_chunk_size,
                    'default_prompt': settings.default_prompt
                }, f)
        except Exception as e:
            logger.error(f"Error saving settings: {str(e)}")

class HistoryDialog(QDialog):
    def __init__(self, parent=None, history=None):
        super().__init__(parent)
        self.history = history or []

        self.setWindowTitle("Search History")
        self.resize(600, 400)

        layout = QVBoxLayout(self)

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Filter history…")
        self.search_field.textChanged.connect(self.filter_history)
        layout.addWidget(self.search_field)

        self.history_list = QListWidget()
        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self.show_context_menu)
        self.history_list.itemDoubleClicked.connect(self.load_article)
        layout.addWidget(self.history_list)

        self.populate_history_list()

    def populate_history_list(self):
        self.history_list.clear()
        for title, _ in self.history:
            self.history_list.addItem(QListWidgetItem(title))

    def filter_history(self):
        txt = self.search_field.text().lower()
        self.history_list.clear()
        for title, _ in self.history:
            if txt in title.lower():
                self.history_list.addItem(QListWidgetItem(title))

    def show_context_menu(self, pos: QPoint):
        item = self.history_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        delete = QAction("Delete", self)
        rename = QAction("Rename", self)
        menu.addAction(delete)
        menu.addAction(rename)
        delete.triggered.connect(lambda: self.delete_item(item))
        rename.triggered.connect(lambda: self.rename_item(item))
        menu.exec_(self.history_list.mapToGlobal(pos))

    def delete_item(self, item: QListWidgetItem):
        title = item.text()
        file_path = os.path.join(self.parent().history_dir, title)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to delete file from disk: {str(e)}")
        self.history = [(t, txt) for t, txt in self.history if t != title]
        self.parent().search_history = self.history
        self.parent().save_history()
        self.populate_history_list()

    def rename_item(self, item: QListWidgetItem):
        old_title = item.text()
        name_only, ext = os.path.splitext(old_title)
        new_base, ok = QInputDialog.getText(
            self,
            "Rename Entry",
            "Enter new title (no extension):",
            text=name_only
        )
        if ok and new_base.strip():
            new_filename = new_base.strip() + ext
            for i, (t, txt) in enumerate(self.history):
                if t == old_title:
                    self.history[i] = (new_filename, txt)
                    break
            self.parent().search_history = self.history
            self.parent().save_history()
            self.populate_history_list()

    def load_article(self, item: QListWidgetItem):
        title = item.text()
        for t, txt in self.history:
            if t == title:
                # create editable article dialog
                dlg = QDialog(self)
                dlg.setWindowTitle(f"History: {title}")
                dlg.resize(800, 600)
                lay = QVBoxLayout(dlg)
                lay.addWidget(QLabel(f"<b>{title}</b>"))
                
                # Add integrated search bar (initially hidden)
                search_container = QWidget()
                search_layout = QHBoxLayout(search_container)
                search_layout.setContentsMargins(0, 0, 0, 0)
                
                search_field = QLineEdit()
                search_field.setPlaceholderText("Search text...")
                search_layout.addWidget(search_field)
                
                case_sensitive = QCheckBox("Case sensitive")
                search_layout.addWidget(case_sensitive)
                
                whole_words = QCheckBox("Whole words")
                search_layout.addWidget(whole_words)
                
                prev_btn = QPushButton("Previous")
                search_layout.addWidget(prev_btn)
                
                next_btn = QPushButton("Next")
                search_layout.addWidget(next_btn)
                
                close_search_btn = QPushButton("×")
                close_search_btn.setFixedSize(25, 25)
                close_search_btn.setToolTip("Close search")
                search_layout.addWidget(close_search_btn)
                
                search_container.setVisible(False)
                lay.addWidget(search_container)

                # text editor
                editor = QTextEdit()
                editor.setPlainText(txt)
                lay.addWidget(editor)

                # Save/close buttons
                btn_layout = QHBoxLayout()
                save_btn = QPushButton("Save")
                save_btn.setEnabled(False)
                btn_layout.addWidget(save_btn)
                close_btn = QPushButton("Close")
                btn_layout.addWidget(close_btn)
                lay.addLayout(btn_layout)

                # track original
                original_text = txt
                
                # Function to toggle search bar visibility
                def toggle_search_bar():
                    search_container.setVisible(not search_container.isVisible())
                    if search_container.isVisible():
                        search_field.setFocus()
                        search_field.selectAll()
                
                # Function to handle search
                def find_text(direction=1):
                    search_text = search_field.text()
                    if not search_text:
                        return
                    
                    # Set search options
                    flags = QTextDocument.FindFlags()
                    if case_sensitive.isChecked():
                        flags |= QTextDocument.FindCaseSensitively
                    if whole_words.isChecked():
                        flags |= QTextDocument.FindWholeWords
                    if direction < 0:
                        flags |= QTextDocument.FindBackward
                    
                    # Perform search
                    cursor = editor.textCursor()
                    # If searching backwards, we need to move cursor to selection start
                    if direction < 0 and cursor.hasSelection():
                        position = cursor.selectionStart()
                        cursor.setPosition(position)
                        editor.setTextCursor(cursor)
                        
                    found = editor.find(search_text, flags)
                    
                    # If not found, try wrapping around
                    if not found:
                        # Save current cursor
                        temp_cursor = editor.textCursor()
                        # Move to beginning/end based on direction
                        cursor = editor.textCursor()
                        if direction > 0:
                            cursor.movePosition(QTextCursor.Start)
                        else:
                            cursor.movePosition(QTextCursor.End)
                        editor.setTextCursor(cursor)
                        
                        # Try search again
                        found = editor.find(search_text, flags)
                        
                        # If still not found, restore original cursor
                        if not found:
                            editor.setTextCursor(temp_cursor)
                            QMessageBox.information(dlg, "Search Result", f"No matches found for '{search_text}'")
                
                # Handle text changes in the editor
                def on_text_changed():
                    save_btn.setEnabled(editor.toPlainText() != original_text)
                
                # Handle save action
                def save_changes():
                    new_text = editor.toPlainText()
                    try:
                        self.parent().update_history_entry(title, new_text)
                        nonlocal original_text
                        original_text = new_text
                        save_btn.setEnabled(False)
                        QMessageBox.information(dlg, "Saved", "Changes have been saved.")
                    except Exception as e:
                        QMessageBox.warning(dlg, "Error", f"Failed to save changes: {e}")
                
                # Connect signals
                editor.textChanged.connect(on_text_changed)
                save_btn.clicked.connect(save_changes)
                close_btn.clicked.connect(dlg.close)
                
                # Search connections
                shortcut_find = QShortcut(QKeySequence("Ctrl+F"), dlg)
                shortcut_find.activated.connect(toggle_search_bar)
                
                close_search_btn.clicked.connect(toggle_search_bar)
                
                search_field.returnPressed.connect(lambda: find_text(1))
                next_btn.clicked.connect(lambda: find_text(1))
                prev_btn.clicked.connect(lambda: find_text(-1))
                
                # Additional keyboard shortcuts for search
                shortcut_find_next = QShortcut(QKeySequence("F3"), dlg)
                shortcut_find_next.activated.connect(lambda: find_text(1))
                
                shortcut_find_prev = QShortcut(QKeySequence("Shift+F3"), dlg)
                shortcut_find_prev.activated.connect(lambda: find_text(-1))
                
                shortcut_close_search = QShortcut(QKeySequence("Escape"), dlg)
                shortcut_close_search.activated.connect(lambda: 
                    search_container.setVisible(False) if search_container.isVisible() else None
                )

                dlg.exec_()
                break


class PdfRagApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF RAG Processor")
        self.resize(1000, 800)
        
        # initialize find dialog reference
        self.shortcut_find = QShortcut(QKeySequence("Ctrl+F"), self)
        self.shortcut_find.activated.connect(self.open_find_dialog)
        self.find_dialog = None

        # load settings object so self.settings exists in closeEvent
        self.settings = SettingsManager.load_settings()

        # Determine directory of this script and create 'rag_history' subfolder
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.history_dir = os.path.join(self.base_dir, "rag_history")
        os.makedirs(self.history_dir, exist_ok=True)
        self.history_file = os.path.join(self.history_dir, "rag_search_history.json")

        # Load persisted search history
        self.load_history()

        # Setup tabs and layouts...
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.manual_tab = QWidget()
        self.qa_tab = QWidget()
        self.init_manual_tab()
        self.init_qa_tab()
        self.tabs.addTab(self.qa_tab, "Smart QA")
        self.tabs.addTab(self.manual_tab, "Manual Processing")
        
        # create and add the new VL tab
        self.vl_tab = QWidget()
        self.init_vl_tab()
        self.tabs.addTab(self.vl_tab, "Visual Explorer")
        self.main_layout.addWidget(self.tabs)

        # Status bar and menu...
        self.status_bar = QtWidgets.QStatusBar()
        self.main_layout.addWidget(self.status_bar)
        self.create_menu_bar()

        # Apply saved settings to your widgets
        self.apply_loaded_settings()
        
        # Cursor management
        self.active_workers = 0
        self.busy_cursor = self.load_custom_cursor("assets/icons/clock.svg")
        
    # Cursor loading method
    def load_custom_cursor(self, path):
        pixmap = QPixmap(path)
        return QCursor(pixmap) if not pixmap.isNull() else QCursor(Qt.WaitCursor)

    # Cursor control methods
    def set_busy_cursor(self):
        self.active_workers += 1
        if self.active_workers == 1:
            QApplication.setOverrideCursor(self.busy_cursor)

    def restore_cursor(self):
        self.active_workers -= 1
        if self.active_workers <= 0:
            QApplication.restoreOverrideCursor()
            self.active_workers = 0

    def load_history(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.search_history = json.load(f)
            else:
                self.search_history = []
        except Exception as e:
            print("Error loading history:", e)
            self.search_history = []
            
    def update_history_entry(self, title: str, new_text: str):
        for i, (t, txt) in enumerate(self.search_history):
            if t == title:
                self.search_history[i] = (t, new_text)
                break
        self.save_history()

    def save_history(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.search_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Error saving history:", e)

    def create_menu_bar(self):
        mb = QMenuBar(self)
        
        # --- History menu ---
        hm = mb.addMenu("History")
        show = QAction("Show History", self)
        show.triggered.connect(self.show_history)
        hm.addAction(show)
        clear = QAction("Clear History", self)
        clear.triggered.connect(self.clear_history)
        hm.addAction(clear)
        
        # --- Help menu ---
        help_menu = mb.addMenu("Help")
        about_action = QAction("About PDF RAG Processor", self)
        about_action.triggered.connect(self.show_app_info)
        help_menu.addAction(about_action)

        # Attach menu bar to layout
        self.layout().setMenuBar(mb)

    def show_app_info(self):
        """Display an About dialog with application information."""
        html = """
        <html>
        <head>
            <style>
                /* Existing styles remain unchanged */
            </style>
        </head>
        <body>
            <h1>PDF RAG Processor</h1>
            <p>
                A desktop application for fast ingestion, indexing,
                and intelligent querying of PDF documents using
                Retrieval-Augmented Generation (RAG).
            </p>

            <h2>Key Features</h2>
            <ul>
                <li><span class="feature">Smart Q&amp;A</span>: Ask natural-language questions and get context-aware answers.</li>
                <li><span class="feature">Manual Processing</span>: Preview, annotate, and correct text before indexing.</li>
                <li><span class="feature">Visual Analysis</span>: Process PDF pages and images with vision-enabled LLMs.</li>
                <li><span class="feature">Bulk PDF Ingestion</span>: Import PDFs and auto-extract text.</li>
                <li><span class="feature">History &amp; Privacy</span>: Review or clear past queries anytime.</li>
                <li><span class="feature">Document Search</span>: Find text in documents with <span class="shortcut">Ctrl+F</span> shortcut.</li>
            </ul>

            <h2>Core Work Modes</h2>
            <ul>
                <li><span class="feature">Smart QA Mode</span>
                    <ul>
                        <li><b>Hybrid semantic + keyword search</b>: This mode combines the power of semantic similarity (understanding the *meaning* of your question) with traditional keyword matching.  The application first finds paragraphs that are semantically similar to your query, and then boosts the score of those paragraphs that also contain your keywords. This provides a balance between finding relevant information even if you don't use the exact wording from the document, and ensuring that important terms are considered.</li>
                        <li><b>Semantic Search Only</b>:  This mode relies solely on semantic similarity to find relevant paragraphs. It uses advanced language models to understand the meaning of your question and identify paragraphs with similar meanings, regardless of the specific keywords used. This is useful when you want to explore broader concepts or paraphrase your query.</li>
                        <li><b>Exact Keyword Matching</b>: This mode performs a simple search for exact keyword matches within the document text. It's fast and precise but may miss relevant information if your question uses different wording than what's in the document.  It is case-insensitive.</li>
                        <li>Adjustable similarity threshold: Control how closely the meaning of the query must match the document content to be considered a hit. Higher thresholds mean stricter matching, lower thresholds are more inclusive.</li>
                        <li>Dynamic context window: The amount of text surrounding each relevant paragraph that's sent to the LLM for generating an answer can be adjusted (Snippet, Full Paragraph, or with surrounding paragraphs).</li>
                    </ul>
                </li>
                <li><span class="feature">Manual Processing Mode</span>
                    <ul>
                        <li>Custom chunk sizes &amp; page ranges:  Break down your PDF into smaller chunks of text to optimize processing and LLM performance. You can also specify which pages to include in the indexing process.</li>
                        <li>Individual prompt tuning: Customize the prompts sent to the LLM for each chunk of text, allowing you to tailor the responses based on the specific content of that chunk.  This is useful when different sections of your document require different instructions.</li>
                        <li>Batch LLM processing with progress bar: Process multiple chunks of text in a batch using an LLM, with a visual progress bar to track the status of each chunk.</li>
                    </ul>
                </li>
                <li><span class="feature">Visual Explorer Mode</span>
                    <ul>
                        <li>Multi-panel layout for visual document analysis: Analyze PDF pages and images side-by-side, allowing you to quickly identify key information.</li>
                        <li>Batch processing of PDF pages and images: Process multiple pages or images simultaneously using vision-enabled LLMs.</li>
                        <li>Adjustable resolution and JPEG quality settings: Optimize image processing costs by adjusting the resolution and compression level of the images.</li>
                        <li>Individual or shared prompts per item: Customize the prompts sent to the LLM for each page or image, allowing you to tailor the responses based on the specific content of that item.</li>
                        <li>Response history tracking and JSON exports: Keep track of your previous responses and export them in a structured JSON format for further analysis.</li>
                    </ul>
                </li>
            </ul>

            <h2>Usage Tips</h2>
            <ol>
                <li>Go to the <span class="feature">Smart QA</span> tab for fast queries.</li>
                <li>Use <span class="feature">Manual Processing</span> to refine extracted text.</li>
                <li>Clear your history under the <span class="feature">History</span> menu regularly.</li>
                <li>In <span class="feature">Visual Explorer</span>, use "Select All/Deselect All" for batch operations.</li>
                <li>Adjust image dimensions in Visual Explorer to optimize processing costs.</li>
                <li>Use individual prompts for different pages/images when needed.</li>
            </ol>

        </body>
        </html>
        """

        dialog = QDialog(self)
        dialog.setWindowTitle("About PDF RAG Processor")
        dialog.resize(600, 550)

        scroll = QScrollArea(dialog)
        scroll.setWidgetResizable(True)

        content = QLabel()
        content.setTextFormat(Qt.RichText)
        content.setText(html)
        content.setWordWrap(True)
        content.setOpenExternalLinks(True)
        scroll.setWidget(content)

        layout = QVBoxLayout(dialog)
        layout.addWidget(scroll)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("close-btn")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)

        dialog.exec_()

    def show_history(self):
        # zawsze wczytujemy świeżą listę
        self.load_history()
        dlg = HistoryDialog(self, self.search_history)
        dlg.exec_()

    def clear_history(self):
        r = QMessageBox.question(self, "Clear History",
                                 "Clear all history?", 
                                 QMessageBox.Yes|QMessageBox.No, QMessageBox.No)
        if r == QMessageBox.Yes:
            # Delete all history files from disk
            for title, _ in self.search_history:
                file_path = os.path.join(self.history_dir, title)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        QMessageBox.warning(
                            self, 
                            "Error", 
                            f"Failed to delete file {title}: {str(e)}"
                        )
            
            # Clear history list
            self.search_history = []
            self.save_history()
            QMessageBox.information(self, "History Cleared", "All history files removed from disk.")

    def init_manual_tab(self):
        # build the manual tab UI with splitter and controls
        layout = QVBoxLayout(self.manual_tab)
        splitter = QSplitter(Qt.Vertical)

        # ===== Upper section: PDF selection and settings =====
        upper_widget = QWidget()
        upper_layout = QVBoxLayout(upper_widget)

        # PDF file path input with enter key support
        self.manual_pdf_path_edit = QLineEdit()
        self.manual_pdf_path_edit.setPlaceholderText("Select PDF file...")
        self.manual_pdf_path_edit.textChanged.connect(self.on_manual_pdf_path_changed)
        self.manual_pdf_path_edit.returnPressed.connect(
            lambda: self.process_manual_pdf() if self.manual_process_btn.isEnabled() else None
        )

        # clear path button
        clear_path_btn = QPushButton("×")
        clear_path_btn.setFixedWidth(24)
        clear_path_btn.setToolTip("Clear path")
        clear_path_btn.clicked.connect(lambda: self.manual_pdf_path_edit.clear())

        # browse file button
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_manual_pdf)

        # assemble PDF selection group
        pdf_group = QGroupBox("PDF Selection")
        pdf_layout = QHBoxLayout()
        pdf_layout.addWidget(self.manual_pdf_path_edit, 1)
        pdf_layout.addWidget(clear_path_btn)
        pdf_layout.addWidget(browse_btn)
        pdf_group.setLayout(pdf_layout)
        upper_layout.addWidget(pdf_group)

        # Page & Token Settings
        settings_group = QGroupBox("Page & Token Settings")
        settings_layout = QGridLayout()
        settings_layout.addWidget(QLabel("Pages from:"), 0, 0)
        self.manual_spin_from = QSpinBox()
        self.manual_spin_from.setMinimum(0)
        settings_layout.addWidget(self.manual_spin_from, 0, 1)
        settings_layout.addWidget(QLabel("to:"), 0, 2)
        self.manual_spin_to = QSpinBox()
        self.manual_spin_to.setMinimum(0)
        settings_layout.addWidget(self.manual_spin_to, 0, 3)
        settings_layout.addWidget(QLabel("Max tokens per chunk:"), 1, 0)
        self.manual_chunk_spin = QSpinBox()
        self.manual_chunk_spin.setRange(1, 1000000)
        self.manual_chunk_spin.setValue(20000)
        settings_layout.addWidget(self.manual_chunk_spin, 1, 1)
        settings_group.setLayout(settings_layout)
        upper_layout.addWidget(settings_group)

        # Process PDF button
        self.manual_process_btn = QPushButton("Process PDF")
        self.manual_process_btn.clicked.connect(self.process_manual_pdf)
        self.manual_process_btn.setEnabled(False)
        upper_layout.addWidget(self.manual_process_btn)

        # Token count / status label under the button
        self.manual_token_label = QLabel("No document selected")
        self.manual_token_label.setStyleSheet("color: #888888; font-style: italic;")
        upper_layout.addWidget(self.manual_token_label)

        # Default Prompt Template
        self.prompt_group = QGroupBox("Default Prompt Template")
        prompt_layout = QVBoxLayout()
        
        # Add checkbox for individual prompts
        self.individual_prompts_checkbox = QCheckBox("Use individual prompts for each chunk")
        self.individual_prompts_checkbox.toggled.connect(self.toggle_individual_prompts)
        prompt_layout.addWidget(self.individual_prompts_checkbox)
        
        self.manual_default_prompt_edit = QPlainTextEdit()
        self.manual_default_prompt_edit.setPlaceholderText("Enter default prompt for all chunks...")
        prompt_layout.addWidget(self.manual_default_prompt_edit)
        self.prompt_group.setLayout(prompt_layout)
        upper_layout.addWidget(self.prompt_group)

        splitter.addWidget(upper_widget)

        # ===== Lower section: Markdown view, progress, prompts, actions =====
        lower_widget = QWidget()
        lower_layout = QVBoxLayout(lower_widget)

        # toggle markdown view (disabled until PDF processed)
        self.manual_markdown_toggle_btn = QPushButton("Show/Edit Markdown")
        self.manual_markdown_toggle_btn.setCheckable(True)
        self.manual_markdown_toggle_btn.setEnabled(False)
        self.manual_markdown_toggle_btn.clicked.connect(self.toggle_manual_markdown_view)
        lower_layout.addWidget(self.manual_markdown_toggle_btn)

        # markdown editor
        self.manual_markdown_editor = QPlainTextEdit()
        self.manual_markdown_editor.setPlaceholderText("Processed Markdown will appear here...")
        self.manual_markdown_editor.setVisible(False)
        lower_layout.addWidget(self.manual_markdown_editor)

        # progress bar
        self.manual_progress_bar = QProgressBar()
        self.manual_progress_bar.setVisible(False)
        lower_layout.addWidget(self.manual_progress_bar)

        # prompts container
        self.manual_prompts_container = QWidget()
        self.manual_prompts_layout = QVBoxLayout(self.manual_prompts_container)
        self.manual_prompts_layout.setAlignment(Qt.AlignTop)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.manual_prompts_container)
        lower_layout.addWidget(scroll)

        # send to LLM button (disabled until PDF processed)
        self.manual_send_btn = QPushButton("Send to LLM")
        self.manual_send_btn.clicked.connect(self.send_manual_to_llm)
        self.manual_send_btn.setEnabled(False)
        lower_layout.addWidget(self.manual_send_btn)

        # save results button (hidden until LLM results arrive)
        self.manual_export_btn = QPushButton("Save Results")
        self.manual_export_btn.clicked.connect(self.export_manual_results)
        self.manual_export_btn.setVisible(False)
        lower_layout.addWidget(self.manual_export_btn)

        splitter.addWidget(lower_widget)
        layout.addWidget(splitter)

        # initialize variables
        self.manual_markdown_text = ''
        self.manual_chunks = []
        self.manual_llm_workers = []
        self.chunk_prompt_inputs = []  # Store references to individual prompt inputs

    def init_qa_tab(self):
        # Constants for better maintainability
        self.MIN_SIMILARITY_DEFAULT = 0.3
        self.TOP_K_DEFAULT = 50
        self.SNIPPET_LENGTH = 500  # characters for snippet mode
        
        # Layout for Smart QA tab with proper spacing
        layout = QVBoxLayout(self.qa_tab)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # ===== PDF Selection Section =====
        pdf_group = QGroupBox("PDF Selection")
        pdf_layout = QHBoxLayout()
        pdf_layout.setSpacing(8)
        
        self.qa_pdf_path_edit = QLineEdit()
        self.qa_pdf_path_edit.setPlaceholderText("Select PDF file...")
        self.qa_pdf_path_edit.textChanged.connect(self.on_qa_pdf_path_changed)
        # Enter key handler for quick processing
        self.qa_pdf_path_edit.returnPressed.connect(lambda: self.process_qa_pdf() if self.qa_process_btn.isEnabled() else None)
        pdf_layout.addWidget(self.qa_pdf_path_edit, 1)
        
        # Clear button inside text field
        clear_path_btn = QPushButton("×")
        clear_path_btn.setFixedWidth(24)
        clear_path_btn.setToolTip("Clear path")
        clear_path_btn.clicked.connect(lambda: self.qa_pdf_path_edit.clear())
        pdf_layout.addWidget(clear_path_btn)
        
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_qa_pdf)
        pdf_layout.addWidget(browse_btn)
        
        pdf_group.setLayout(pdf_layout)
        layout.addWidget(pdf_group)
        
        # ===== Process Controls Section =====
        process_layout = QHBoxLayout()
        process_layout.setSpacing(8)
        
        self.qa_process_btn = QPushButton("Process PDF")
        self.qa_process_btn.clicked.connect(self.process_qa_pdf)
        self.qa_process_btn.setEnabled(False)  # Disabled by default until valid PDF is selected
        process_layout.addWidget(self.qa_process_btn)
        
        # Status label with better visual feedback
        self.qa_status_label = QLabel("No document loaded")
        self.qa_status_label.setStyleSheet("color: #888888; font-style: italic;")
        process_layout.addWidget(self.qa_status_label, 1)
        
        layout.addLayout(process_layout)
        
        # Progress bar with percentage display
        self.qa_progress_bar = QProgressBar()
        self.qa_progress_bar.setVisible(False)
        self.qa_progress_bar.setFormat("%p% - %v/%m pages processed")
        layout.addWidget(self.qa_progress_bar)
        
        # ===== Search Mode & Settings Section =====
        settings_group = QGroupBox("Search Mode & Settings")
        settings_layout = QGridLayout()
        settings_layout.setSpacing(8)
        settings_layout.setColumnStretch(1, 1)  # Make the second column stretch

        # Mode selector with better labels
        settings_layout.addWidget(QLabel("Search Mode:"), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Semantic + Keyword Boost",
            "Semantic Search Only",
            "Exact Keyword Matching"
        ])
        self.mode_combo.setToolTip(
            "Select search mode:\n"
            "- Semantic + Keyword Boost: combine semantic similarity with keyword hits\n"
            "- Semantic Search Only: use only semantic similarity\n"
            "- Exact Keyword Matching: match exact keywords only"
        )
        # Update UI when mode changes
        self.mode_combo.currentIndexChanged.connect(self.update_search_ui_state)
        settings_layout.addWidget(self.mode_combo, 0, 1)

        # Minimum similarity with percentage display
        settings_layout.addWidget(QLabel("Min Similarity:"), 1, 0)
        self.min_similarity_spin = QDoubleSpinBox()
        self.min_similarity_spin.setRange(0.0, 1.0)
        self.min_similarity_spin.setSingleStep(0.05)
        self.min_similarity_spin.setValue(self.MIN_SIMILARITY_DEFAULT)
        self.min_similarity_spin.setDecimals(2)
        self.min_similarity_spin.setSuffix("%")
        self.min_similarity_spin.setSpecialValueText("0% (Include All)")
        self.min_similarity_spin.setToolTip(
            "Minimum semantic similarity threshold (0.0–1.0). Higher → stricter matching."
        )
        settings_layout.addWidget(self.min_similarity_spin, 1, 1)

        # Top K results with better range
        settings_layout.addWidget(QLabel("Top K Results:"), 2, 0)
        self.top_k_spin = QSpinBox()
        self.top_k_spin.setRange(1, 999)
        self.top_k_spin.setValue(self.TOP_K_DEFAULT)
        self.top_k_spin.setSuffix(" paragraphs")
        self.top_k_spin.setToolTip(
            "Maximum number of paragraphs to retrieve."
        )
        settings_layout.addWidget(self.top_k_spin, 2, 1)

        # ===== Context mode with better descriptions =====
        settings_layout.addWidget(QLabel("Context Mode:"), 3, 0)
        self.context_mode_combo = QComboBox()
        self.context_mode_combo.addItems([
            f"Snippet (first {self.SNIPPET_LENGTH} chars)",
            "Full Paragraph",
            "Full Paragraph + Surrounding 1 paragraph",
            "Full Paragraph + Surrounding 2 paragraphs"
        ])
        self.context_mode_combo.setToolTip(
            f"Snippet: send first {self.SNIPPET_LENGTH} chars of each paragraph.\n"
            "Full Paragraph: send entire paragraph only.\n"
            "Full Paragraph + Surrounding 1/2: send paragraph plus 1/2 paragraphs before/after."
        )
        settings_layout.addWidget(self.context_mode_combo, 3, 1)

        # Additional prompt instructions with scroll area for better space usage
        settings_layout.addWidget(QLabel("Extra Instructions:"), 4, 0, Qt.AlignTop)
        self.custom_prompt_edit = QPlainTextEdit()
        self.custom_prompt_edit.setPlaceholderText(
            "Enter additional instructions for the LLM prompt...\n"
            "Example: 'Focus on technical details' or 'Explain in simple terms'"
        )
        self.custom_prompt_edit.setToolTip(
            "These lines will be appended to the built prompt as custom instructions."
        )
        self.custom_prompt_edit.setMaximumHeight(60)  # Limit height to save space
        settings_layout.addWidget(self.custom_prompt_edit, 4, 1)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # ===== QA Input Section =====
        qa_input_group = QGroupBox("Ask Document")
        input_layout = QVBoxLayout()
        input_layout.setSpacing(8)
        
        # Question input with enter key handling
        self.qa_question = QLineEdit()
        self.qa_question.setPlaceholderText("Type your question about the document...")
        # Connect Enter key to search button
        self.qa_question.returnPressed.connect(lambda: self.handle_qa_search() if self.qa_search_btn.isEnabled() else None)
        input_layout.addWidget(self.qa_question)
        
        self.qa_search_btn = QPushButton("Find Answers")
        self.qa_search_btn.clicked.connect(self.handle_qa_search)
        self.qa_search_btn.setEnabled(False)  # Disabled until document is processed
        input_layout.addWidget(self.qa_search_btn)
        
        qa_input_group.setLayout(input_layout)
        layout.addWidget(qa_input_group)
        
        # ===== Results Section =====
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout()
        results_layout.setSpacing(8)
        
        self.qa_results = QTextEdit()
        self.qa_results.setReadOnly(True)
        self.qa_results.setPlaceholderText("Results will appear here after processing your question...")
        self.qa_results.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.qa_results.setAcceptRichText(True)  # Allow rich text for better formatting
        results_layout.addWidget(self.qa_results)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        # ===== Save QA Results Button (hidden initially) =====
        self.qa_export_btn = QPushButton("Save QA Results")
        self.qa_export_btn.setVisible(False)
        self.qa_export_btn.clicked.connect(self.export_qa_results)
        layout.addWidget(self.qa_export_btn)
        
        # Set stretch factors to make results expandable
        layout.setStretchFactor(pdf_group, 0)
        layout.setStretchFactor(settings_group, 0)
        layout.setStretchFactor(qa_input_group, 0)
        layout.setStretchFactor(results_group, 1)  # Results should expand to fill space
        
        # Initialize variables
        self.qa_markdown_text = ''
        self.qa_document_processed = False
        self.qa_document_path = ''
        
        # Initial UI state update
        self.update_search_ui_state()
        
    def toggle_individual_prompts(self, checked):
        # Show/hide the default prompt based on checkbox state
        self.manual_default_prompt_edit.setVisible(not checked)
        
        # Re-populate the prompts to show individual inputs if applicable
        if self.manual_chunks:
            self.populate_manual_prompts()
    
    def copy_prompt_to_all(self):
        if not self.chunk_prompt_inputs or len(self.chunk_prompt_inputs) <= 1:
            return
            
        # Get text from first prompt input
        first_prompt_text = self.chunk_prompt_inputs[0].toPlainText()
        
        # Copy to all other prompt inputs
        for prompt_input in self.chunk_prompt_inputs[1:]:
            prompt_input.setPlainText(first_prompt_text)

    def update_search_ui_state(self):
        """Update UI elements based on selected search mode."""
        mode_index = self.mode_combo.currentIndex()
        
        # Enable/disable similarity settings based on mode
        semantic_mode = mode_index in [0, 1]  # Semantic+Boost or Semantic Only
        self.min_similarity_spin.setEnabled(semantic_mode)
        
        # Format percentage display correctly
        self.min_similarity_spin.setPrefix('')
        self.min_similarity_spin.setSuffix('%')
        # Convert decimal to percentage display
        current_value = self.min_similarity_spin.value()
        self.min_similarity_spin.setValue(current_value)
        self.min_similarity_spin.setSpecialValueText("0% (Include All)")

    def browse_manual_pdf(self):
        # Open file dialog for manual PDF selection
        path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if path:
            self.manual_pdf_path_edit.setText(path)
            # Immediately load PDF info when a new file is selected
            self.load_manual_pdf_info()

    def browse_qa_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if path:
            self.qa_pdf_path_edit.setText(path)
            self.on_qa_pdf_path_changed()

    def on_manual_pdf_path_changed(self):
        # validate PDF path, enable/disable controls, update label color/style
        path = self.manual_pdf_path_edit.text().strip()
        is_valid = path.lower().endswith('.pdf') and os.path.isfile(path)
        # update process button
        self.manual_process_btn.setEnabled(is_valid)
        # dependent controls remain disabled until processing finishes
        self.manual_markdown_toggle_btn.setEnabled(False)
        self.manual_send_btn.setEnabled(False)
        if not path:
            self.manual_token_label.setText("No document selected")
            self.manual_token_label.setStyleSheet("color: #888888; font-style: italic;")
        elif is_valid:
            name = os.path.basename(path)
            self.manual_token_label.setText(f"Ready to process: {name}")
            self.manual_token_label.setStyleSheet("color: #006400; font-style: normal;")
            # Also load PDF info here to handle cases where path is pasted or edited
            self.load_manual_pdf_info()
        else:
            self.manual_token_label.setText("Invalid PDF file selected")
            self.manual_token_label.setStyleSheet("color: #8B0000; font-style: italic;")

    def on_qa_pdf_path_changed(self):
        # Trigger loading of QA PDF info when path changes
        path = self.qa_pdf_path_edit.text().strip()
        
        # Path validation
        is_valid_pdf = path.lower().endswith('.pdf') and os.path.isfile(path)
        
        # Update button and status
        self.qa_process_btn.setEnabled(is_valid_pdf)
        
        # Update status label
        if not path:
            self.qa_status_label.setText("No document loaded")
            self.qa_status_label.setStyleSheet("color: #888888; font-style: italic;")
        elif is_valid_pdf:
            self.qa_status_label.setText(f"Ready to process: {os.path.basename(path)}")
            self.qa_status_label.setStyleSheet("color: #006400; font-style: normal;")
            self.load_qa_pdf_info()  # Existing functionality
        else:
            self.qa_status_label.setText("Invalid PDF file selected")
            self.qa_status_label.setStyleSheet("color: #8B0000; font-style: italic;")
            
        # New line - disable search button when document changes
        self.qa_search_btn.setEnabled(False)
        
        if is_valid_pdf:
            self.qa_status_label.setText(f"Ready to process: {os.path.basename(path)}")
            self.qa_status_label.setStyleSheet("color: #006400; font-style: normal;")
            self.load_qa_pdf_info()

    def load_manual_pdf_info(self):
        # Load PDF info and set spinbox values
        path = self.manual_pdf_path_edit.text().strip()
        if not path.lower().endswith('.pdf') or not os.path.isfile(path):
            return  # Return early if path is invalid
        
        page_count, error = PdfProcessor.load_document(path)
        if error:
            QMessageBox.warning(self, "PDF Error", error)
            return
        
        # For 1-based indexing (if your UI shows page numbers starting from 1):
        last_page = page_count
        
        # Set maximum values based on actual page count
        self.manual_spin_from.setMaximum(last_page)
        self.manual_spin_to.setMaximum(last_page)
        
        # Store max page for correction
        self.manual_spin_from.setProperty("max_page", last_page)
        self.manual_spin_to.setProperty("max_page", last_page)
        
        # Always set to full range
        self.manual_spin_from.setValue(1)  # Start from page 1
        self.manual_spin_to.setValue(last_page)  # End at last page
        
        # Save only the path to settings
        self.settings.last_pdf_path_manual = path
        SettingsManager.save_settings(self.settings)

    def load_qa_pdf_info(self):
        # Load PDF info for QA tab
        path = self.qa_pdf_path_edit.text().strip()
        page_count, error = PdfProcessor.load_document(path)
        if error:
            QMessageBox.warning(self, "PDF Error", error)
            return
        self.settings.last_pdf_path_qa = path
        SettingsManager.save_settings(self.settings)

    def correct_spinbox_value(self):
        # Correct spinbox value to max page if necessary
        sender = self.sender()
        max_page = sender.property("max_page")
        if max_page is not None and sender.value() > max_page:
            sender.setValue(max_page)
            
        # Also check if from_page > to_page and correct if needed
        if sender == self.manual_spin_from and self.manual_spin_from.value() > self.manual_spin_to.value():
            self.manual_spin_from.setValue(self.manual_spin_to.value())
        elif sender == self.manual_spin_to and self.manual_spin_to.value() < self.manual_spin_from.value():
            self.manual_spin_to.setValue(self.manual_spin_from.value())

    def toggle_manual_markdown_view(self):
        # Toggle visibility of markdown editor
        is_visible = self.manual_markdown_editor.isVisible()
        self.manual_markdown_editor.setVisible(not is_visible)

    def process_manual_pdf(self):
        # Process PDF for manual tab
        pdf_path = self.manual_pdf_path_edit.text().strip()
        if not pdf_path or not os.path.isfile(pdf_path):
            QMessageBox.warning(self, "Error", "Invalid PDF file selected.")
            return
        
        # First, get the actual page count from the PDF
        page_count, error = PdfProcessor.load_document(pdf_path)
        if error:
            QMessageBox.warning(self, "Error", f"Failed to load PDF: {error}")
            return
        
        # Get the user-entered page range (assuming 1-based indexing in UI)
        from_page = self.manual_spin_from.value()
        to_page = self.manual_spin_to.value()
        
        # Adjust page range if it exceeds the actual page count
        if from_page > page_count:
            from_page = page_count  # Set to max page number (1-based)
            self.manual_spin_from.setValue(from_page)
            
        if to_page > page_count:
            to_page = page_count  # Set to max page number (1-based)
            self.manual_spin_to.setValue(to_page)
        
        # Make sure from_page is not greater than to_page
        if from_page > to_page:
            from_page = to_page
            self.manual_spin_from.setValue(from_page)
        
        # Save only necessary settings (not the page range)
        self.settings.last_chunk_size = self.manual_chunk_spin.value()
        self.settings.default_prompt = self.manual_default_prompt_edit.toPlainText()
        SettingsManager.save_settings(self.settings)
        
        # Convert from 1-based indexing (UI) to 0-based indexing (PDF library)
        pdf_from_page = from_page - 1
        pdf_to_page = to_page - 1
        
        # Create a page list based on the adjusted values
        pages = list(range(pdf_from_page, pdf_to_page + 1))
        
        self.manual_progress_bar.setVisible(True)
        self.manual_progress_bar.setRange(0, 0)
        self.manual_process_btn.setEnabled(False)
        
        self.manual_worker = PdfProcessingWorker(pdf_path, pages, self.manual_chunk_spin.value())
        self.manual_worker.finished.connect(self.on_manual_pdf_processing_finished)
        self.manual_worker.start()
    
    def process_qa_pdf(self):
        # Process entire PDF for QA tab
        pdf_path = self.qa_pdf_path_edit.text().strip()
        if not pdf_path or not os.path.isfile(pdf_path):
            QMessageBox.warning(self, "Error", "Invalid PDF file selected.")
            return
        
        page_count, error = PdfProcessor.load_document(pdf_path)
        if error:
            QMessageBox.warning(self, "PDF Error", error)
            return
        pages = list(range(0, page_count))  # Process all pages
        
        self.qa_progress_bar.setVisible(True)
        self.qa_progress_bar.setRange(0, 0)
        self.qa_process_btn.setEnabled(False)
        
        # Reset search button state when starting new processing
        self.qa_search_btn.setEnabled(False)
        
        self.qa_progress_bar.setVisible(True)
        self.qa_progress_bar.setRange(0, 0)
        self.qa_process_btn.setEnabled(False)
        
        self.qa_worker = PdfProcessingWorker(pdf_path, pages)
        self.qa_worker.finished.connect(self.on_qa_pdf_processing_finished)
        self.qa_worker.start()

    def on_manual_pdf_processing_finished(self, markdown: str, chunks: List[str], error: str):
        # hide progress, re-enable Process button, update UI, enable other actions
        self.manual_progress_bar.setVisible(False)
        self.manual_process_btn.setEnabled(True)

        if error:
            QMessageBox.critical(self, "Processing Error", error)
            self.manual_token_label.setText("Processing failed")
            self.manual_token_label.setStyleSheet("color: #8B0000; font-style: italic;")
            return

        self.manual_markdown_text = markdown
        self.manual_chunks = chunks
        self.manual_markdown_editor.setPlainText(markdown)

        total_tokens = TokenCounter.count_tokens(markdown)
        self.manual_token_label.setText(f"Tokens: {total_tokens} | Chunks: {len(chunks)}")
        self.manual_token_label.setStyleSheet("color: #006400; font-style: normal;")

        # enable markdown view and send button once processing is complete
        self.manual_markdown_toggle_btn.setEnabled(True)
        self.manual_send_btn.setEnabled(True)

        self.populate_manual_prompts()

    def on_qa_pdf_processing_finished(self, markdown: str, chunks: List[str], error: str):
        # Handle QA PDF processing completion
        self.qa_progress_bar.setVisible(False)
        self.qa_process_btn.setEnabled(True)
        
        success = not error  # We define success based on the absence of errors
        
        if error:
            QMessageBox.critical(self, "Processing Error", error)
            self.qa_status_label.setText("Document processing failed")
            self.qa_status_label.setStyleSheet("color: #8B0000; font-style: italic;")
            self.qa_search_btn.setEnabled(False)
            return
        
        # Code executed only when processing is successful
        self.qa_markdown_text = markdown
        self.status_bar.showMessage("PDF processed for Smart QA", 5000)
        
        self.qa_search_btn.setEnabled(True)
        self.qa_status_label.setText(f"Document ready: {os.path.basename(self.qa_document_path)}")
        self.qa_status_label.setStyleSheet("color: #006400; font-style: normal;")

    def populate_manual_prompts(self):
        # Remove any existing widgets
        for i in reversed(range(self.manual_prompts_layout.count())):
            w = self.manual_prompts_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        
        # Clear the stored reference list
        self.chunk_prompt_inputs = []

        # Add each chunk as its own group with a selectable preview
        for idx, chunk in enumerate(self.manual_chunks):
            chunk_group = QGroupBox(f"Chunk {idx+1}")
            chunk_layout = QVBoxLayout(chunk_group)

            # Show up to 500 characters in the preview (or the full chunk if shorter)
            text = chunk if len(chunk) <= 500 else chunk[:500] + "…"
            preview = QLabel(f"Preview: {text}")
            preview.setWordWrap(True)

            # Allow mouse & keyboard text selection for copying
            preview.setTextInteractionFlags(
                Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
            )
            # Optional: enable keyboard focus so you can navigate/select with keys
            preview.setFocusPolicy(Qt.StrongFocus)

            chunk_layout.addWidget(preview)
            
            # Add individual prompt input if checkbox is checked
            if self.individual_prompts_checkbox.isChecked():
                if idx == 0:
                    # Create a horizontal layout for the first chunk to include a "Copy to all" button
                    prompt_header_layout = QHBoxLayout()
                    prompt_label = QLabel("Prompt:")
                    prompt_header_layout.addWidget(prompt_label)
                    
                    copy_to_all_btn = QPushButton("Copy to all")
                    copy_to_all_btn.clicked.connect(self.copy_prompt_to_all)
                    prompt_header_layout.addWidget(copy_to_all_btn, alignment=Qt.AlignRight)
                    chunk_layout.addLayout(prompt_header_layout)
                else:
                    # Just add a label for other chunks
                    chunk_layout.addWidget(QLabel("Prompt:"))
                
                # Create the prompt text input
                prompt_input = QPlainTextEdit()
                prompt_input.setPlaceholderText(f"Enter prompt for chunk {idx+1}...")
                
                # Get default text from the global prompt if available
                if not self.individual_prompts_checkbox.isChecked():
                    prompt_input.setPlainText(self.manual_default_prompt_edit.toPlainText())
                
                # Set a reasonable height for the prompt input
                prompt_input.setMaximumHeight(100)
                chunk_layout.addWidget(prompt_input)
                
                # Store reference to this input
                self.chunk_prompt_inputs.append(prompt_input)
            
            self.manual_prompts_layout.addWidget(chunk_group)

    def send_manual_to_llm(self):
        if not self.manual_chunks:
            QMessageBox.warning(self, "Error", "No data to send. Process PDF first.")
            return

        # Reset previous workers
        for w in self.manual_llm_workers:
            if w.isRunning():
                w.quit()
                w.wait()
        
        # Initialize new workers
        self.manual_llm_workers = []
        self.all_llm_responses = []
        self.manual_progress_bar.setRange(0, len(self.manual_chunks))
        self.manual_progress_bar.setValue(0)
        self.manual_progress_bar.setVisible(True)
        self.manual_send_btn.setEnabled(False)
        self.manual_export_btn.setVisible(False)

        # Create and connect workers for each chunk
        for idx, chunk in enumerate(self.manual_chunks):
            # Determine which prompt to use
            if self.individual_prompts_checkbox.isChecked() and idx < len(self.chunk_prompt_inputs):
                # Use individual prompt for this chunk
                prompt = self.chunk_prompt_inputs[idx].toPlainText().strip()
            else:
                # Use default prompt
                prompt = self.manual_default_prompt_edit.toPlainText().strip()
                
            worker = LlmWorker(idx, prompt, chunk)
            worker.result_ready.connect(self.on_manual_llm_result)
            worker.started.connect(self.set_busy_cursor)
            worker.finished.connect(self.restore_cursor)
            self.manual_llm_workers.append(worker)
            worker.start()

    def on_manual_llm_result(self, idx, response, error):
        # Update GUI with response
        container = self.manual_prompts_layout.itemAt(idx).widget()
        layout = container.layout()
        
        txt = error or response
        edit = QPlainTextEdit()
        edit.setReadOnly(True)
        edit.setPlainText(txt)
        layout.addWidget(edit)

        # Update progress
        self.all_llm_responses.append(txt)
        self.manual_progress_bar.setValue(self.manual_progress_bar.value() + 1)

        # Final cleanup check
        if self.manual_progress_bar.value() == len(self.manual_chunks):
            self.manual_send_btn.setEnabled(True)
            self.manual_export_btn.setVisible(True)
            self.manual_progress_bar.setVisible(False)
            
            # Force cursor restore if any workers left
            if self.active_workers > 0:
                self.active_workers = 0
                QApplication.restoreOverrideCursor()

    def export_manual_results(self):
        if not self.manual_chunks:
            QMessageBox.warning(self, "Error", "No data to export.")
            return

        # build export payload
        data = {
            "pdf_path": self.manual_pdf_path_edit.text(),
            "page_range": [self.manual_spin_from.value(), self.manual_spin_to.value()],
            "token_count": TokenCounter.count_tokens(self.manual_markdown_text),
            "chunks": []
        }
        for idx, chunk in enumerate(self.manual_chunks):
            data["chunks"].append({
                "chunk_idx": idx,
                "content": chunk,
                "prompt": self.manual_default_prompt_edit.toPlainText(),
                "response": self.all_llm_responses[idx] if idx < len(self.all_llm_responses) else ""
            })

        # ask user for base filename (without extension)
        base_pdf_name = os.path.splitext(os.path.basename(self.manual_pdf_path_edit.text()))[0]
        suggested_name, ok = QInputDialog.getText(
            self,
            "Save Results",
            "Enter filename (no extension):",
            text=base_pdf_name + "_rag_results"
        )
        if not ok or not suggested_name.strip():
            return
        filename = suggested_name.strip() + ".json"
        save_path = os.path.join(self.history_dir, filename)

        # write JSON file
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self.status_bar.showMessage(f"Saved JSON to {save_path}", 5000)

        # record this export in history
        combined = "\n\n".join(ch["response"] for ch in data["chunks"])
        self.search_history.append((filename, combined))
        self.save_history()
        self.status_bar.showMessage(f"History updated with {filename}", 5000)
        
    def export_qa_results(self):
        # Ensure there is something to save
        if not self.qa_markdown_text:
            QMessageBox.warning(self, "Error", "No QA results to save.")
            return

        # Prepare JSON payload
        data = {
            "pdf_path": self.qa_document_path,
            "question": self.qa_question.text().strip(),
            "answer": self.qa_markdown_text
        }

        # Derive default filename from the PDF basename
        pdf_base = os.path.splitext(os.path.basename(self.qa_pdf_path_edit.text().strip()))[0]
        default_name = f"{pdf_base}_qa_results"

        # Ask user for filename
        suggested_name, ok = QInputDialog.getText(
            self,
            "Save QA Results",
            "Enter filename (no extension):",
            text=default_name
        )
        if not ok or not suggested_name.strip():
            return
        filename = suggested_name.strip() + ".json"
        save_path = os.path.join(self.history_dir, filename)

        # Write JSON to disk
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.status_bar.showMessage(f"Saved QA JSON to {save_path}", 5000)

            # Update history
            self.search_history.append((filename, self.qa_markdown_text))
            self.save_history()
            self.status_bar.showMessage(f"History updated with {filename}", 5000)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save QA results: {e}")

    def handle_qa_search(self):
        question = self.qa_question.text().strip()
        if not question:
            QMessageBox.warning(self, "Error", "Please enter a question first.")
            return

        # Disable UI and set cursor
        self.set_busy_cursor()
        self.qa_search_btn.setEnabled(False)
        self.qa_status_label.setText("Processing...")
        QApplication.processEvents()

        # Get parameters
        mode = self.mode_combo.currentText()
        min_sim = self.min_similarity_spin.value()
        top_k = self.top_k_spin.value()
        context_mode = self.context_mode_combo.currentText()
        custom_instr = self.custom_prompt_edit.toPlainText()

        # Create and start worker
        self.qa_worker = QaWorker(
            self.qa_markdown_text,
            question,
            mode,
            min_sim,
            top_k,
            context_mode,
            custom_instr,
            self.SNIPPET_LENGTH
        )
        self.qa_worker.finished.connect(self.on_qa_success)
        self.qa_worker.error.connect(self.on_qa_error)
        self.qa_worker.start()

    # QA success handler
    def on_qa_success(self, result_text, relevant_sections):
        self.restore_cursor()
        self.qa_results.setPlainText(result_text)
        self.qa_status_label.setText("Ready")
        self.qa_markdown_text = result_text
        self.qa_export_btn.setVisible(True)
        self.qa_export_btn.setEnabled(True)
        self.qa_search_btn.setEnabled(True)

    # QA error handler
    def on_qa_error(self, error_msg):
        self.restore_cursor()
        self.qa_status_label.setText("Error")
        self.qa_search_btn.setEnabled(True)
        QMessageBox.critical(self, "Processing Error", error_msg)

    def apply_loaded_settings(self):
        # Apply loaded settings on startup
        if self.settings.last_pdf_path_manual and os.path.exists(self.settings.last_pdf_path_manual):
            self.manual_pdf_path_edit.setText(self.settings.last_pdf_path_manual)
            self.load_manual_pdf_info()  # This will set the full page range
        if self.settings.last_pdf_path_qa and os.path.exists(self.settings.last_pdf_path_qa):
            self.qa_pdf_path_edit.setText(self.settings.last_pdf_path_qa)
            self.load_qa_pdf_info()
        self.manual_chunk_spin.setValue(self.settings.last_chunk_size)
        self.manual_default_prompt_edit.setPlainText(self.settings.default_prompt)
        
    def open_find_dialog(self):
        if self.find_dialog is None:
            # pass the markdown editor as the target widget
            self.find_dialog = FindDialog(self.manual_markdown_editor, self)
        self.find_dialog.show()
        self.find_dialog.raise_()
        self.find_dialog.search_field.setFocus()

    def closeEvent(self, event):
        # Save settings on close - but not page range values
        self.settings.last_pdf_path_manual = self.manual_pdf_path_edit.text()
        self.settings.last_pdf_path_qa = self.qa_pdf_path_edit.text()
        self.settings.last_chunk_size = self.manual_chunk_spin.value()
        self.settings.default_prompt = self.manual_default_prompt_edit.toPlainText()
        SettingsManager.save_settings(self.settings)
        event.accept()
        

    def init_vl_tab(self):
        """
        Build the Visual Explorer tab with three-panel layout using QSplitter:
        1. File selection and pages/images list (left)
        2. Page/image preview (middle) - toggleable via checkbox
        3. Prompt and LLM Response (right)
        """
        # Create main horizontal layout for the Visual Explorer tab
        main_layout = QHBoxLayout(self.vl_tab)

        # Create a QSplitter to allow dynamic resizing of panels
        self.main_splitter = QSplitter(Qt.Horizontal)

        # -------------------- LEFT PANEL --------------------
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # File chooser group
        file_group = QGroupBox("File Selection")
        h_file = QHBoxLayout(file_group)
        h_file.addWidget(QLabel("File:"))
        self.le_file_path = QLineEdit()
        self.le_file_path.setReadOnly(True)
        h_file.addWidget(self.le_file_path)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self.on_vl_browse)
        h_file.addWidget(btn_browse)
        left_layout.addWidget(file_group)

        # Image settings group
        settings_group = QGroupBox("Image Settings")
        settings_layout = QGridLayout(settings_group)
        settings_layout.addWidget(QLabel("Max Width (px):"), 0, 0)
        self.sb_max_width = QtWidgets.QSpinBox()
        self.sb_max_width.setRange(256, 2048)
        self.sb_max_width.setValue(768)
        self.sb_max_width.setSingleStep(64)
        settings_layout.addWidget(self.sb_max_width, 0, 1)
        settings_layout.addWidget(QLabel("Max Height (px):"), 1, 0)
        self.sb_max_height = QtWidgets.QSpinBox()
        self.sb_max_height.setRange(256, 2048)
        self.sb_max_height.setValue(1366)
        self.sb_max_height.setSingleStep(64)
        settings_layout.addWidget(self.sb_max_height, 1, 1)
        settings_layout.addWidget(QLabel("JPEG Quality:"), 2, 0)
        self.sb_quality = QtWidgets.QSpinBox()
        self.sb_quality.setRange(10, 95)
        self.sb_quality.setValue(75)
        self.sb_quality.setSingleStep(5)
        settings_layout.addWidget(self.sb_quality, 2, 1)
        settings_layout.addWidget(QLabel("Show Preview:"), 3, 0)
        self.cb_show_preview = QCheckBox()
        self.cb_show_preview.setChecked(True)
        self.cb_show_preview.stateChanged.connect(self.toggle_preview_panel)
        settings_layout.addWidget(self.cb_show_preview, 3, 1)
        left_layout.addWidget(settings_group)

        # Check all/none buttons and controls
        check_group = QGroupBox("Selection Controls")
        check_layout = QHBoxLayout(check_group)
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.clicked.connect(self.select_all_items)
        check_layout.addWidget(self.btn_select_all)
        self.btn_select_none = QPushButton("Deselect All")
        self.btn_select_none.clicked.connect(self.deselect_all_items)
        check_layout.addWidget(self.btn_select_none)
        left_layout.addWidget(check_group)

        # Items list group with checkboxes
        items_group = QGroupBox("Items")
        items_layout = QVBoxLayout(items_group)
        self.list_items = QListWidget()
        self.list_items.setSelectionMode(QListWidget.SingleSelection)
        self.list_items.currentRowChanged.connect(self.on_item_selected)
        items_layout.addWidget(self.list_items)
        left_layout.addWidget(items_group, stretch=1)

        # Add the left_panel widget to the splitter
        self.main_splitter.addWidget(left_panel)

        # -------------------- MIDDLE PANEL --------------------
        self.middle_panel = QWidget()
        middle_layout = QVBoxLayout(self.middle_panel)
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        preview_container = QWidget()
        preview_container_layout = QVBoxLayout(preview_container)
        self.lbl_preview = QLabel("No item selected")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        preview_container_layout.addWidget(self.lbl_preview)
        preview_container_layout.addStretch()
        scroll_area.setWidget(preview_container)
        preview_layout.addWidget(scroll_area)
        middle_layout.addWidget(preview_group)

        # Add the middle_panel widget to the splitter
        self.main_splitter.addWidget(self.middle_panel)

        # -------------------- RIGHT PANEL --------------------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Prompt section
        prompt_group = QGroupBox("Prompt Settings")
        prompt_layout = QVBoxLayout(prompt_group)

        # Header z checkboxem i copy-to-all
        prompt_header = QHBoxLayout()
        prompt_header.addWidget(QLabel("Default Prompt:"))
        self.cb_individual_prompts = QCheckBox("Use Individual Prompts")
        self.cb_individual_prompts.setChecked(False)
        self.cb_individual_prompts.stateChanged.connect(self.vl_toggle_individual_prompts)
        prompt_header.addWidget(self.cb_individual_prompts)

        self.btn_copy_to_all = QPushButton("Copy to All from Page 1")
        self.btn_copy_to_all.clicked.connect(self.copy_prompt_to_all)
        self.btn_copy_to_all.setVisible(False)
        prompt_header.addWidget(self.btn_copy_to_all)

        prompt_layout.addLayout(prompt_header)

        # Stack widget: strona 0 = default prompt, strona 1 = indywidualne
        self.prompt_stack = QStackedWidget()
        # strona 0
        self.te_default_prompt = QPlainTextEdit()
        self.te_default_prompt.setPlaceholderText("Enter default prompt for all selected images...")
        self.prompt_stack.addWidget(self.te_default_prompt)
        # strona 1
        self.individual_prompts_widget = QWidget()
        individual_layout = QVBoxLayout(self.individual_prompts_widget)
        self.prompt_scroll_area = QScrollArea()
        self.prompt_scroll_area.setWidgetResizable(True)
        self.prompt_scroll_area.setMinimumHeight(300)
        self.prompt_container = QWidget()
        self.prompt_container_layout = QVBoxLayout(self.prompt_container)
        self.prompt_scroll_area.setWidget(self.prompt_container)
        individual_layout.addWidget(self.prompt_scroll_area)
        self.prompt_stack.addWidget(self.individual_prompts_widget)

        # Dodajemy stack do layoutu
        prompt_layout.addWidget(self.prompt_stack)

        # Buttons for processing
        btn_layout = QHBoxLayout()
        self.btn_run_all = QPushButton("Process Selected")
        self.btn_run_all.clicked.connect(self.process_selected_items)
        btn_layout.addWidget(self.btn_run_all)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.cancel_processing)
        self.btn_cancel.setEnabled(False)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save Results")
        self.btn_save.clicked.connect(self.save_vl_results)
        self.btn_save.setEnabled(False)
        btn_layout.addWidget(self.btn_save)

        prompt_layout.addLayout(btn_layout)
        right_layout.addWidget(prompt_group)
        
        # Progress section - initially hidden
        progress_group = QGroupBox("Progress")
        self.progress_group = progress_group  # Store reference for visibility toggle
        progress_layout = QVBoxLayout(progress_group)
        self.vl_progress_bar = QProgressBar()
        self.vl_progress_bar.setRange(0, 100)
        self.vl_progress_bar.setValue(0)
        progress_layout.addWidget(self.vl_progress_bar)
        self.lbl_progress_status = QLabel("Ready")
        progress_layout.addWidget(self.lbl_progress_status)
        right_layout.addWidget(progress_group)
        progress_group.setVisible(False)  # Initially hidden
        
        # LLM Response section - initially hidden
        response_group = QGroupBox("LLM Responses")
        self.response_group = response_group  # Store reference for visibility toggle
        response_layout = QVBoxLayout(response_group)
        self.te_vl_responses = QTextEdit()
        self.te_vl_responses.setReadOnly(True)
        response_layout.addWidget(self.te_vl_responses)
        right_layout.addWidget(response_group, stretch=1)
        response_group.setVisible(False)  # Initially hidden

        # Add the right_panel widget to the splitter
        self.main_splitter.addWidget(right_panel)

        # Set initial stretch factors: left=1, middle=2, right=1
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setStretchFactor(2, 1)

        # Finally, add the splitter to the main layout
        main_layout.addWidget(self.main_splitter)

        # Initialize data structures for holding the loaded files
        self.vl_items = []  # List to hold all items (PDF pages or images)
        self.vl_doc = None  # PDF document if opened
        self.vl_prompts = {}  # Dictionary to store individual prompts {index: prompt}
        self.vl_responses = {}  # Dictionary to store responses {index: response}
        self.processing_cancelled = False  # Flag for cancellation
        self.processing_thread = None  # Will hold the processing thread

    def select_all_items(self):
        """Select all items in the list."""
        for i in range(self.list_items.count()):
            item = self.list_items.item(i)
            item.setCheckState(Qt.Checked)
        
        # Update individual prompts if enabled
        if self.cb_individual_prompts.isChecked():
            self.update_individual_prompts()

    def deselect_all_items(self):
        """Deselect all items in the list."""
        for i in range(self.list_items.count()):
            item = self.list_items.item(i)
            item.setCheckState(Qt.Unchecked)
        
        # Update individual prompts if enabled
        if self.cb_individual_prompts.isChecked():
            self.update_individual_prompts()

    def vl_toggle_individual_prompts(self, state):
        """Toggle between default prompt and individual prompts."""
        if state == Qt.Checked:
            # Pokaż indywidualne i przycisk copy
            self.prompt_stack.setCurrentIndex(1)
            self.btn_copy_to_all.setVisible(True)

            # Jeśli jest domyślny prompt, zainicjuj nim wszystkie
            default_txt = self.te_default_prompt.toPlainText().strip()
            if default_txt:
                for idx in range(len(self.vl_items)):
                    self.vl_prompts.setdefault(idx, default_txt)

            self.update_individual_prompts()

        else:
            # Pokaż stronę z default promptem
            self.prompt_stack.setCurrentIndex(0)
            self.btn_copy_to_all.setVisible(False)

            # Jeśli były indywidualne, ustaw pierwszy niepusty jako domyślny
            for prompt in self.vl_prompts.values():
                if prompt.strip():
                    self.te_default_prompt.setPlainText(prompt)
                    break

    def update_individual_prompts(self):
        """Update the individual prompts panel based on selected items."""
        # Clear existing widgets
        self.clear_individual_prompts()
        
        # Create a widget for each selected item
        selected_indices = self.get_selected_indices()
        
        if not selected_indices:
            # No selections, show message
            label = QLabel("No items selected. Select items from the list.")
            self.prompt_container_layout.addWidget(label)
            return
        
        # Create prompt widgets for each selected item
        for idx in selected_indices:
            item = self.vl_items[idx]
            name = item['name']
            
            # Create a group box for each item
            group = QGroupBox(name)
            group_layout = QVBoxLayout(group)
            
            # Create text edit for prompt
            prompt_edit = QPlainTextEdit()
            prompt_edit.setPlaceholderText(f"Enter prompt for {name}...")
            
            # If we have a saved prompt for this index, load it
            if idx in self.vl_prompts:
                prompt_edit.setPlainText(self.vl_prompts[idx])
            else:
                # Otherwise use the default prompt
                prompt_edit.setPlainText(self.te_default_prompt.toPlainText())
            
            # Store the widget for later access
            prompt_edit.setObjectName(f"prompt_{idx}")
            prompt_edit.textChanged.connect(lambda idx=idx, edit=prompt_edit: self.save_individual_prompt(idx, edit))
            group_layout.addWidget(prompt_edit)
            
            # Add response area if we have a response
            if idx in self.vl_responses and self.vl_responses[idx]:
                response_label = QLabel("Response:")
                group_layout.addWidget(response_label)
                
                response_text = QTextEdit()
                response_text.setReadOnly(True)
                response_text.setPlainText(self.vl_responses[idx])
                response_text.setMaximumHeight(150)
                group_layout.addWidget(response_text)
            
            self.prompt_container_layout.addWidget(group)
        
        # Add stretch at the end
        self.prompt_container_layout.addStretch()
        
    def update_progress(self, value, status):
        """Update the progress bar and status label."""
        self.vl_progress_bar.setValue(value)
        self.lbl_progress_status.setText(status)

    def on_task_completed(self, index, response):
        """Handle a completed task from the processing thread."""
        # Store the response
        self.vl_responses[index] = response
        
        # Show response group if this is the first response
        if not self.response_group.isVisible():
            self.response_group.setVisible(True)
        
        # Update the main response text area
        current_text = self.te_vl_responses.toPlainText()
        item_name = self.vl_items[index]['name']
        
        if current_text:
            current_text += "\n\n"
        
        self.te_vl_responses.setPlainText(
            current_text + 
            f"--- {item_name} ---\n" +
            response
        )
        
        # Scroll to bottom
        self.te_vl_responses.verticalScrollBar().setValue(
            self.te_vl_responses.verticalScrollBar().maximum()
        )
        
        # Update individual prompts display if visible
        if self.cb_individual_prompts.isChecked():
            self.update_individual_prompts()

    def on_all_tasks_completed(self):
        """Handle completion of all tasks."""
        # Hide the progress group when all tasks are completed
        self.progress_group.setVisible(False)

        # Restore cursor to default
        QApplication.restoreOverrideCursor()

        # Update UI
        self.btn_run_all.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_save.setEnabled(len(self.vl_responses) > 0)

        # Final status update
        total_processed = len(self.vl_responses)
        self.lbl_progress_status.setText(f"Completed {total_processed} items")
        
    def cancel_processing(self):
        """Cancel the processing of items."""
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_cancelled = True
            self.lbl_progress_status.setText("Cancelling...")
            self.btn_cancel.setEnabled(False)
            # Restore cursor to default on cancel
            QApplication.restoreOverrideCursor()

    def clear_individual_prompts(self):
        """Clear all widgets from the individual prompts container."""
        # Remove all widgets from the container
        while self.prompt_container_layout.count():
            item = self.prompt_container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def save_individual_prompt(self, index, edit):
        """Save the prompt text for a specific index."""
        self.vl_prompts[index] = edit.toPlainText()

    def copy_prompt_to_all(self):
        """Copy the first prompt to all other selected items."""
        selected_indices = self.get_selected_indices()
        if not selected_indices:
            return
        
        # Get text from the first prompt
        first_prompt = None
        for idx in selected_indices:
            prompt_edit = self.prompt_container.findChild(QPlainTextEdit, f"prompt_{idx}")
            if prompt_edit:
                first_prompt = prompt_edit.toPlainText()
                break
        
        if not first_prompt:
            return
        
        # Copy to all other prompts
        for idx in selected_indices:
            prompt_edit = self.prompt_container.findChild(QPlainTextEdit, f"prompt_{idx}")
            if prompt_edit:
                prompt_edit.setPlainText(first_prompt)
                self.vl_prompts[idx] = first_prompt

    def get_selected_indices(self):
        """Get indices of all checked items."""
        selected = []
        for i in range(self.list_items.count()):
            if self.list_items.item(i).checkState() == Qt.Checked:
                selected.append(i)
        return selected

    def process_selected_items(self):
        """Process all selected items by sending them to the LLM."""
        # change cursor to clock
        QApplication.setOverrideCursor(QCursor(QPixmap("assets/icons/clock.svg")))

        selected_indices = self.get_selected_indices()
        if not selected_indices:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "No Selection", "Please select at least one item first.")
            return

        # Get default prompt if not using individual prompts
        default_prompt = self.te_default_prompt.toPlainText().strip()
        if not self.cb_individual_prompts.isChecked() and not default_prompt:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "No Prompt", "Enter a prompt for the selected items.")
            return

        # Check if all selected items have prompts when using individual prompts
        if self.cb_individual_prompts.isChecked():
            missing_prompts = []
            for idx in selected_indices:
                if idx not in self.vl_prompts or not self.vl_prompts[idx].strip():
                    missing_prompts.append(self.vl_items[idx]['name'])
            if missing_prompts:
                QApplication.restoreOverrideCursor()
                QMessageBox.warning(
                    self,
                    "Missing Prompts",
                    "Please enter prompts for all selected items:\n- " + "\n- ".join(missing_prompts)
                )
                return

        # Show progress group
        self.progress_group.setVisible(True)

        # Prepare task list
        tasks = []
        for idx in selected_indices:
            item = self.vl_items[idx]
            prompt = (self.vl_prompts.get(idx, default_prompt)
                      if self.cb_individual_prompts.isChecked()
                      else default_prompt)
            tasks.append({'index': idx, 'item': item, 'prompt': prompt})

        # Clear responses and update UI
        for idx in selected_indices:
            self.vl_responses.pop(idx, None)
        self.te_vl_responses.clear()
        self.vl_progress_bar.setValue(0)
        self.lbl_progress_status.setText("Starting...")

        # Update UI state
        self.btn_run_all.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_save.setEnabled(False)
        self.processing_cancelled = False

        # Create and start the processing thread
        self.processing_thread = ProcessingThread(self, tasks)
        self.processing_thread.progress_updated.connect(self.update_progress)
        self.processing_thread.task_completed.connect(self.on_task_completed)
        self.processing_thread.all_completed.connect(self.on_all_tasks_completed)
        self.processing_thread.start()

    def toggle_preview_panel(self, state):
        """
        Show or hide the preview panel based on checkbox state
        """
        if state == Qt.Checked:
            self.middle_panel.show()
        else:
            self.middle_panel.hide()
    
    def on_vl_browse(self):
        """
        Open a file dialog to select a PDF or images, then populate the items list.
        """
        # Define supported image formats
        image_formats = "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff)"
        pdf_format = "PDF Files (*.pdf)"
        all_formats = f"{pdf_format};;{image_formats};;All Files (*.*)"
        
        paths, selected_filter = QFileDialog.getOpenFileNames(
            self, "Open Files", "", all_formats
        )
        
        if not paths:
            return
        
        # Clear previous items
        self.list_items.clear()
        self.vl_items = []
        self.vl_prompts = {}
        self.vl_responses = {}
        
        # Reset PDF document if we had one
        if hasattr(self, 'vl_doc') and self.vl_doc is not None:
            self.vl_doc.close()
            self.vl_doc = None
        
        # Process all selected files
        for path in paths:
            file_ext = os.path.splitext(path)[1].lower()
            
            if file_ext == '.pdf':
                # Handle PDF - add each page as an item
                pdf_doc = fitz.open(path)
                self.vl_doc = pdf_doc  # Store for later use
                
                for i in range(pdf_doc.page_count):
                    item_name = f"{os.path.basename(path)} - Page {i+1}"
                    
                    # Create item with checkbox
                    item = QListWidgetItem(item_name)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Unchecked)
                    
                    self.list_items.addItem(item)
                    self.vl_items.append({
                        'type': 'pdf_page',
                        'pdf_path': path,
                        'page_num': i,
                        'doc': pdf_doc,
                        'name': item_name
                    })
            
            elif file_ext in ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tif', '.tiff']:
                # Handle image files
                item_name = os.path.basename(path)
                
                # Create item with checkbox
                item = QListWidgetItem(item_name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                
                self.list_items.addItem(item)
                self.vl_items.append({
                    'type': 'image',
                    'path': path,
                    'name': item_name
                })
        
        # Select the first item if available
        if self.list_items.count() > 0:
            self.list_items.setCurrentRow(0)
        
        # Set the file path display to show multiple files or a single file
        if len(paths) == 1:
            self.le_file_path.setText(paths[0])
        else:
            self.le_file_path.setText(f"{len(paths)} files selected")
        
        # Clear prompt panels
        self.clear_individual_prompts()
        self.btn_save.setEnabled(False)
            

    def on_item_selected(self, row: int):
        """
        Display the selected item (PDF page or image) in the preview panel.
        Adjust resolution input fields to match the original size of the selected item.
        """
        if row < 0 or row >= len(self.vl_items):
            return
        
        item = self.vl_items[row]
        
        if item['type'] == 'pdf_page':
            # Handle PDF page
            page = item['doc'][item['page_num']]
            pix = page.get_pixmap(dpi=75)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(img)
            
            # Calculate original page dimensions at standard DPI (72 dpi is standard)
            # This gives us more reasonable default values for width/height settings
            width_pt = page.rect.width
            height_pt = page.rect.height
            
            # Convert points to pixels at 72 DPI (1 point = 1/72 inch)
            width_px = int(width_pt)
            height_px = int(height_pt)
            
            # Update resolution fields to match page dimensions but cap at min/max values of spinbox
            self.sb_max_width.setValue(
                max(min(width_px, self.sb_max_width.maximum()), self.sb_max_width.minimum())
            )
            self.sb_max_height.setValue(
                max(min(height_px, self.sb_max_height.maximum()), self.sb_max_height.minimum())
            )
            
        elif item['type'] == 'image':
            # Handle image file
            pixmap = QPixmap(item['path'])
            
            # Update resolution fields to match the original image dimensions
            # Cap at min/max values of spinbox
            self.sb_max_width.setValue(
                max(min(pixmap.width(), self.sb_max_width.maximum()), self.sb_max_width.minimum())
            )
            self.sb_max_height.setValue(
                max(min(pixmap.height(), self.sb_max_height.maximum()), self.sb_max_height.minimum())
            )
        
        # Display the image
        self.lbl_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.lbl_preview.setScaledContents(False)
        self.lbl_preview.setPixmap(pixmap)
        self.lbl_preview.adjustSize()
            
    def save_vl_results(self):
        """Save the results to a JSON file and add to history."""
        if not self.vl_responses:
            QMessageBox.warning(self, "Error", "No responses to save.")
            return
        
        # Build export payload
        data = {
            "source_files": [],
            "date_processed": datetime.datetime.now().isoformat(),
            "items": []
        }
        
        # Track unique source files
        source_files = set()
        
        for idx, response in self.vl_responses.items():
            item = self.vl_items[idx]
            
            # Add source file info
            if item['type'] == 'pdf_page':
                source_files.add(item['pdf_path'])
            else:
                source_files.add(item['path'])
            
            # Get the prompt used
            prompt = self.vl_prompts.get(idx, self.te_default_prompt.toPlainText()) \
                if self.cb_individual_prompts.isChecked() else self.te_default_prompt.toPlainText()
            
            # Add item details
            data["items"].append({
                "name": item['name'],
                "type": item['type'],
                "source": item['pdf_path'] if item['type'] == 'pdf_page' else item['path'],
                "page_number": item['page_num'] if item['type'] == 'pdf_page' else None,
                "prompt": prompt,
                "response": response
            })
        
        # Add source files list
        data["source_files"] = list(source_files)
        
        # Ask user for base filename
        if len(source_files) == 1:
            suggested_name = os.path.splitext(os.path.basename(list(source_files)[0]))[0] + "_vl_results"
        else:
            suggested_name = "multiple_files_vl_results"
        
        filename, ok = QInputDialog.getText(
            self,
            "Save Results",
            "Enter filename (no extension):",
            text=suggested_name
        )
        
        if not ok or not filename.strip():
            return
        
        filename = filename.strip() + ".json"
        save_path = os.path.join(self.history_dir, filename)
        
        # Write JSON file
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self.status_bar.showMessage(f"Saved JSON to {save_path}", 5000)
        
        # Record this export in history - combine all responses
        combined = "\n\n".join([
            f"--- {item['name']} ---\n{item['response']}" 
            for item in data["items"]
        ])
        
        self.search_history.append((filename, combined))
        self.save_history()
        self.status_bar.showMessage(f"History updated with {filename}", 5000)

# Main entry point
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    window = PdfRagApp()
    window.show()
    sys.exit(app.exec_())