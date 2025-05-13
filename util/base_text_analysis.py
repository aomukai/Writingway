#!/usr/bin/env python
"""
base_text_analysis.py

Base module containing common text analysis logic that can be used across languages.
Language-specific data is provided by the respective language modules.
"""

import spacy
from collections import Counter, defaultdict
import re

class BaseTextAnalysis:
    def __init__(self, model_name, language_data):
        self.model_name = model_name
        self.language_data = language_data
        self.nlp = None

    def initialize(self):
        """Initializes the spaCy model for the selected language."""
        if self.nlp is not None:
            return True
        try:
            self.nlp = spacy.load(self.model_name)
            return True
        except OSError:
            return False

    def analyze_text(self, text, target_grade):
        """Analyzes the text at the sentence level. This method can be overridden by language-specific subclasses."""
        doc = self.nlp(text)
        annotated_sentences = []
        for sent in doc.sents:
            sent_text = sent.text.strip()
            if len(sent_text.split()) < 5:
                continue
            start = sent.start_char
            end = sent.end_char
            # To be defined in subclasses
            grade = self.calculate_readability(sent_text)
            is_complex = grade > target_grade
            annotated_sentences.append({
                "sentence": sent_text,
                "start": start,
                "end": end,
                "grade": grade,
                "complex": is_complex,
                "doc": sent
            })
        return annotated_sentences

    def calculate_readability(self, text):
        """Must be implemented in the language-specific subclass."""
        raise NotImplementedError("The calculate_readability method must be implemented in the subclass.")

    def detect_passive(self, sentence_text, tokens):
        """Detects passive voice based on language-specific dependency tags."""
        passive_deps = self.language_data.get("passive_deps", {"nsubjpass", "auxpass"})
        agent_markers = self.language_data.get("agent_markers", {"by"})
        for token in tokens:
            if token.dep_ in passive_deps:
                if any(t.dep_ == "agent" or t.text.lower() in agent_markers for t in tokens):
                    return [(0, len(sentence_text))]
        return []

    def detect_weak_formulations(self, sentence_text, doc):
        """Detects weak formulations based on language-specific patterns and keywords."""
        spans = []
        weak_patterns = self.language_data.get("weak_patterns", [])
        weak_terms = self.language_data.get("weak_terms", set())
        
        for pattern in weak_patterns:
            for match in re.finditer(pattern, sentence_text, re.IGNORECASE):
                spans.append((match.start(), match.end()))
        
        for term in weak_terms:
            pattern = r'\b' + re.escape(term) + r'\b'
            for match in re.finditer(pattern, sentence_text, re.IGNORECASE):
                spans.append((match.start(), match.end()))
        
        spans.sort(key=lambda span: span[0])
        return spans

    def detect_nonstandard_speech_verbs(self, text):
        """Detects non-standard speech verbs."""
        doc = self.nlp(text)
        standard_verbs = self.language_data.get("standard_speech_verbs", {"say", "ask"})
        speech_verbs = self.language_data.get("speech_verbs", {"say", "ask"})
        spans = []
        for token in doc:
            if token.pos_ == "VERB" and token.lemma_.lower() in speech_verbs:
                if token.lemma_.lower() not in standard_verbs:
                    spans.append((token.idx, token.idx + len(token.text), "non_standard_dialogue_tag"))
        return spans

    def detect_filter_words(self, doc):
        """Detects filter words."""
        filter_words = self.language_data.get("filter_words", set())
        results = []
        for token in doc:
            if token.lemma_.lower() in filter_words:
                results.append((token.idx, token.idx + len(token.text), token.text))
        return results

    def detect_telling_not_showing(self, doc):
        """Detects 'telling' instead of 'showing'."""
        telling_verbs = self.language_data.get("telling_verbs", {"be", "feel", "seem"})
        emotion_words = self.language_data.get("emotion_words", set())
        results = []
        for i, token in enumerate(doc):
            if token.lemma_.lower() in telling_verbs:
                max_lookahead = min(4, len(doc) - i)
                for j in range(1, max_lookahead):
                    if doc[i+j].lemma_.lower() in emotion_words:
                        phrase = doc[i:i+j+1].text
                        results.append((doc[i].idx, doc[i+j].idx + len(doc[i+j].text), phrase))
                        break
        return results

    def analyze_verb_strength(self, doc):
        """Analyzes the strength of verbs."""
        weak_verbs = self.language_data.get("weak_verbs", {"be"})
        results = []
        for token in doc:
            if token.lemma_.lower() in weak_verbs and token.dep_ == "ROOT":
                results.append((token.idx, token.idx + len(token.text), token.text, "weak_verb"))
        return results

    def detect_overused_words(self, text, doc, threshold=3, window_size=1000, ignore_common=True):
        """Detects overused words."""
        common_words = self.language_data.get("common_words", set())
        word_positions = defaultdict(list)
        for token in doc:
            if token.is_punct or (ignore_common and token.lower_ in common_words):
                continue
            if token.is_alpha and len(token.text) > 2:
                word_positions[token.lower_].append((token.idx, token.idx + len(token.text), token.text))
        results = []
        for word, positions in word_positions.items():
            if len(positions) >= threshold:
                processed_positions = set()
                for i, (start, end, text) in enumerate(positions):
                    if start in processed_positions:
                        continue
                    window_occurrences = sum(1 for pos, unused, unused in positions if abs(pos - start) <= window_size)
                    if window_occurrences >= threshold:
                        results.append((start, end, word, window_occurrences))
                        processed_positions.add(start)
        return results

    def check_pronoun_clarity(self, doc):
        """Checks the clarity of pronouns."""
        results = []
        for sent in doc.sents:
            entities = defaultdict(list)
            for token in sent:
                if token.pos_ == "PROPN" or token.ent_type_:
                    gender = token.morph.get("Gender", ["unknown"])[0]
                    entities[gender].append(token.text)
            for token in sent:
                if token.pos_ == "PRON":
                    gender = token.morph.get("Gender", ["unknown"])[0]
                    if gender in entities and len(entities[gender]) >= 2:
                        results.append((token.idx, token.idx + len(token.text), token.text))
        return results

    def analyze_dialogue_balance(self, text):
        """Analyzes the balance of dialogues."""
        quote_pattern = self.language_data.get("quote_pattern", r'"[^"]*"')
        dialogue_matches = list(re.finditer(quote_pattern, text))
        dialogue_chars = sum(match.end() - match.start() for match in dialogue_matches)
        total_chars = len(text)
        dialogue_ratio = dialogue_chars / total_chars if total_chars > 0 else 0
        paragraphs = re.split(r'\n\s*\n', text)
        dialogue_heavy_paragraphs = []
        for para in paragraphs:
            if not para.strip():
                continue
            para_start = text.find(para)
            para_end = para_start + len(para)
            para_dialogue_chars = sum(
                min(match.end(), para_end) - max(match.start(), para_start)
                for match in dialogue_matches
                if max(match.start(), para_start) < min(match.end(), para_end)
            )
            para_ratio = para_dialogue_chars / len(para) if len(para) > 0 else 0
            if para_ratio > 0.7 and len(para) > 100:
                dialogue_heavy_paragraphs.append((para_start, para_end))
        return dialogue_ratio, dialogue_heavy_paragraphs

    def detect_repeated_sentence_starts(self, doc, threshold=3):
        """Detects repeated sentence starters."""
        sentence_starters = []
        starter_positions = defaultdict(list)
        for sent in doc.sents:
            first_word = next((token for token in sent if token.is_alpha and not token.is_stop), None)
            if first_word:
                starter = first_word.lemma_.lower()
                sentence_starters.append(starter)
                starter_positions[starter].append((sent.start_char, first_word.idx + len(first_word.text)))
        starter_counts = Counter(sentence_starters)
        results = []
        for starter, positions in starter_positions.items():
            if starter_counts[starter] >= threshold:
                for start, end in positions:
                    results.append((start, end, starter))
        return results

    def comprehensive_analysis(self, text, target_grade=8):
        """Performs a comprehensive analysis of the text."""
        if not self.nlp:
            raise RuntimeError(f"spaCy model for {self.model_name} has not been loaded.")
        doc = self.nlp(text)
        sentence_analysis = self.analyze_text(text, target_grade)
        results = {
            "sentence_analysis": sentence_analysis,
            "weak_formulations": [],
            "passive_voice": [],
            "nonstandard_speech": self.detect_nonstandard_speech_verbs(text),
            "filter_words": [],
            "telling_not_showing": [],
            "weak_verbs": [],
            "overused_words": self.detect_overused_words(text, doc),
            "pronoun_clarity": self.check_pronoun_clarity(doc),
            "dialogue_ratio": 0.0,
            "dialogue_heavy_sections": [],
            "repeated_sentence_starts": self.detect_repeated_sentence_starts(doc)
        }
        dialogue_ratio, dialogue_heavy_sections = self.analyze_dialogue_balance(text)
        results["dialogue_ratio"] = dialogue_ratio
        results["dialogue_heavy_sections"] = dialogue_heavy_sections
        
        for sent_data in sentence_analysis:
            sent_doc = sent_data["doc"]
            sent_start = sent_data["start"]
            sent_text = sent_data["sentence"]
            
            for start, end in self.detect_weak_formulations(sent_text, sent_doc):
                results["weak_formulations"].append((sent_start + start, sent_start + end))
            for start, end in self.detect_passive(sent_text, sent_doc):
                results["passive_voice"].append((sent_start + start, sent_start + end))
            for start, end, word in self.detect_filter_words(sent_doc):
                results["filter_words"].append((sent_start + start, sent_start + end, word))
            for start, end, phrase in self.detect_telling_not_showing(sent_doc):
                results["telling_not_showing"].append((sent_start + start, sent_start + end, phrase))
            for start, end, construction, verb_type in self.analyze_verb_strength(sent_doc):
                results["weak_verbs"].append((sent_start + start, sent_start + end, construction, verb_type))
        
        return results
