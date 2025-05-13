#!/usr/bin/env python
"""
statistics.py

This module provides functionality for analyzing and displaying statistics
about a writing project, including:
- Word counts (total, by act/chapter/scene)
- Character mentions and dialogue
- Writing metrics from text_analysis.py
- Compendium usage statistics
- Writing progress over time
"""

import os
import json
import re
import datetime
from collections import defaultdict, Counter
import statistics as stats

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QLabel, 
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QSplitter,
    QFrame, QScrollArea, QProgressBar, QComboBox, QGridLayout, QMessageBox, QFileDialog
)
from PyQt5.QtGui import QPainter
from PyQt5.QtCore import Qt
from PyQt5.QtChart import QChart, QChartView, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis, QLineSeries

from settings.theme_manager import ThemeManager

# Import text analysis functionality
# from text_analysis import nlp, comprehensive_analysis

class ProjectStatistics:
    """
    Handles the collection and processing of statistics for a project.
    """
    def __init__(self, project_path):
        """
        Initialize with the path to the project folder.
        
        Args:
            project_path (str): Path to the project directory
        """
        # Convert to absolute path to avoid working directory issues
        self.project_path = os.path.abspath(project_path)
        self.project_name = os.path.basename(self.project_path)
        
        print(f"Initializing statistics for project: {self.project_name}")
        print(f"Using absolute path: {self.project_path}")
        
        # Initialize all attributes to prevent AttributeError
        self.compendium_data = {}
        self.scene_contents = {}
        self.scene_metadata = {}
        self.word_counts = {}
        self.analysis_results = {}
        self.character_mentions = defaultdict(list)
        self.location_mentions = defaultdict(list)
        self.custom_mentions = defaultdict(list)
        self.word_count_history = []
        
    def load_data(self):
        """
        Load all project data needed for statistics analysis.
        
        Returns:
            bool: True if data was loaded successfully, False otherwise
        """
        # Debug output
        print(f"Loading project data from: {self.project_path}")
        print(f"Current working directory: {os.getcwd()}")
        
        try:
            files_in_dir = os.listdir(self.project_path)
            print(f"Files in project directory: {files_in_dir}")
        except Exception as e:
            print(f"ERROR: Cannot list files in '{self.project_path}': {str(e)}")
            return False
        
        # Load compendium data
        compendium_path = os.path.join(self.project_path, "compendium.json")
        if os.path.exists(compendium_path):
            try:
                with open(compendium_path, 'r', encoding='utf-8') as f:
                    self.compendium_data = json.load(f)
                    print(f"Successfully loaded compendium from {compendium_path}")
                    print(f"Compendium data type: {type(self.compendium_data)}")
                    
                    # If it's a list, convert to a simple dictionary format to make processing easier
                    if isinstance(self.compendium_data, list):
                        print("Converting list compendium data to dictionary format")
                        converted_data = {
                            "items": self.compendium_data
                        }
                        self.compendium_data = converted_data
            except Exception as e:
                print(f"Error loading compendium: {e}")
                self.compendium_data = {}
        else:
            print(f"Compendium file not found at {compendium_path}")
            self.compendium_data = {}
        
        # Updated: Look for HTML files instead of TXT files
        scene_files = [f for f in os.listdir(self.project_path) if f.endswith('.html')]
        print(f"Found {len(scene_files)} potential scene files")
        
        for scene_file in scene_files:
            try:
                file_path = os.path.join(self.project_path, scene_file)
                
                # Try to extract metadata from the filename
                try:
                    metadata = self._parse_scene_filename(scene_file)
                except Exception as e:
                    print(f"Could not parse filename for {scene_file}, using defaults: {str(e)}")
                    metadata = {
                        'id': scene_file.replace('.html', ''),
                        'project': self.project_name,
                        'act': 'Unknown',
                        'chapter': 'Unknown',
                        'scene': 'Unknown',
                        'timestamp': os.path.getmtime(file_path),
                        'filename': scene_file
                    }
                
                # Read file content and extract text from HTML using BeautifulSoup
                with open(file_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                content = soup.get_text()
                print(f"Successfully extracted {len(content)} characters from {scene_file}")
                
                # Store content and metadata
                self.scene_contents[metadata['id']] = content
                self.scene_metadata[metadata['id']] = metadata
                
                # Calculate basic word count
                self.word_counts[metadata['id']] = len(content.split())
                
                # Add to history based on timestamp (if string, parse, otherwise use as is)
                if isinstance(metadata['timestamp'], str):
                    try:
                        timestamp = datetime.datetime.strptime(metadata['timestamp'], '%Y%m%d%H%M%S')
                    except ValueError:
                        try:
                            timestamp = datetime.datetime.fromtimestamp(float(metadata['timestamp']))
                        except ValueError:
                            timestamp = datetime.datetime.now()
                else:
                    timestamp = datetime.datetime.fromtimestamp(metadata['timestamp'])
                
                self.word_count_history.append({
                    'date': timestamp.strftime('%Y-%m-%d'),
                    'time': timestamp.strftime('%H:%M:%S'),
                    'scene_id': metadata['id'],
                    'act': metadata['act'],
                    'chapter': metadata['chapter'],
                    'scene': metadata['scene'],
                    'word_count': len(content.split())
                })
                
            except Exception as e:
                print(f"Error processing scene file {scene_file}: {e}")
        
        print(f"Successfully loaded {len(self.scene_contents)} scenes")
        
        # Sort word count history by timestamp
        self.word_count_history.sort(key=lambda x: datetime.datetime.strptime(f"{x['date']} {x['time']}", '%Y-%m-%d %H:%M:%S'))
        
        if self.scene_contents:
            try:
                self._process_scene_data()
                return True
            except Exception as e:
                print(f"Error processing scene data: {e}")
                return False
        else:
            print("No scene data was loaded!")
            return False
   
    def _parse_scene_filename(self, filename):
        """
        Parse a scene filename to extract metadata.
        
        Format: ProjectName-Act#-Chapter#-Scene#_YYYYMMDDHHMMSS.html
        
        Args:
            filename (str): The scene filename to parse
            
        Returns:
            dict: Metadata extracted from the filename
        """
        # Remove the .html extension
        base_name = filename.replace('.html', '')
        
        # Split into parts
        parts = base_name.split('_')
        timestamp = parts[1] if len(parts) > 1 else ""
        
        # Parse project-act-chapter-scene
        structure_parts = parts[0].split('-')
        if len(structure_parts) >= 4:
            project = structure_parts[0]
            act = structure_parts[1]
            chapter = structure_parts[2]
            scene = structure_parts[3]
        else:
            # Handle cases where the filename doesn't match expected format
            project = self.project_name
            act = "Unknown"
            chapter = "Unknown"
            scene = "Unknown"
        
        scene_id = f"{act}-{chapter}-{scene}"
        
        return {
            'id': scene_id,
            'project': project,
            'act': act,
            'chapter': chapter,
            'scene': scene,
            'timestamp': timestamp,
            'filename': filename
        }
    
    def _process_scene_data(self):
        """
        Process all scene data to generate statistics.
        This includes text analysis, character/location mentions, etc.
        """
        # Reset collections
        self.character_mentions = defaultdict(list)
        self.location_mentions = defaultdict(list)
        self.custom_mentions = defaultdict(list)
        self.analysis_results = {}

        # Lazy import to avoid circular import issues:
        from .text_analysis import comprehensive_analysis

        # Extract categories from compendium if available
        characters = {}
        locations = {}
        custom_categories = {}

        if self.compendium_data:
            try:
                # Check if compendium_data is a dictionary or a list
                if isinstance(self.compendium_data, dict):
                    # Process dictionary format
                    for category_name, entries in self.compendium_data.items():
                        if isinstance(entries, dict):  # Make sure entries is also a dict
                            if category_name.lower() == "characters":
                                characters = entries
                            elif category_name.lower() == "locations":
                                locations = entries
                            else:
                                custom_categories[category_name] = entries
                elif isinstance(self.compendium_data, list):
                    # Process list format
                    print(f"Warning: Compendium data is in list format with {len(self.compendium_data)} items")
                    # You could implement a different parsing logic here based on your data structure
                else:
                    print(f"Warning: Unexpected compendium data type: {type(self.compendium_data)}")
            except Exception as e:
                print(f"Error processing compendium data: {e}")

        # Process each scene
        for scene_id, content in self.scene_contents.items():
            # Run text analysis
            try:
                self.analysis_results[scene_id] = comprehensive_analysis(content)
            except Exception as e:
                print(f"Error analyzing scene {scene_id}: {e}")
                self.analysis_results[scene_id] = {}

            # Find character mentions
            if characters:
                try:
                    for char_name, char_data in characters.items():
                        if char_name.lower() in content.lower():
                            mention_count = content.lower().count(char_name.lower())
                            self.character_mentions[char_name].append({
                                'scene_id': scene_id,
                                'count': mention_count
                            })
                except Exception as e:
                    print(f"Error processing character mentions: {e}")

            # Find location mentions
            if locations:
                try:
                    for loc_name, loc_data in locations.items():
                        if loc_name.lower() in content.lower():
                            mention_count = content.lower().count(loc_name.lower())
                            self.location_mentions[loc_name].append({
                                'scene_id': scene_id,
                                'count': mention_count
                            })
                except Exception as e:
                    print(f"Error processing location mentions: {e}")

            # Find custom category mentions
            try:
                for category_name, entries in custom_categories.items():
                    if isinstance(entries, dict):  # Make sure entries is a dict
                        for entry_name, entry_data in entries.items():
                            if entry_name.lower() in content.lower():
                                mention_count = content.lower().count(entry_name.lower())
                                self.custom_mentions[category_name].append({
                                    'entry': entry_name,
                                    'scene_id': scene_id,
                                    'count': mention_count
                                })
            except Exception as e:
                print(f"Error processing custom category mentions: {e}")

    
    def get_word_count_stats(self):
        """
        Get word count statistics for the project.
        
        Returns:
            dict: Word count statistics
        """
        if not self.word_counts:
            return {
                'total': 0,
                'by_act': {},
                'by_chapter': {},
                'by_scene': self.word_counts,
                'average_scene': 0,
                'average_chapter': 0
            }
        
        # Calculate aggregated word counts
        by_act = defaultdict(int)
        by_chapter = defaultdict(int)
        
        for scene_id, count in self.word_counts.items():
            metadata = self.scene_metadata.get(scene_id, {})
            act = metadata.get('act', 'Unknown')
            chapter = metadata.get('chapter', 'Unknown')
            
            by_act[act] += count
            by_chapter[f"{act}-{chapter}"] += count
        
        # Calculate averages
        scene_counts = list(self.word_counts.values())
        avg_scene = sum(scene_counts) / len(scene_counts) if scene_counts else 0
        
        chapter_counts = list(by_chapter.values())
        avg_chapter = sum(chapter_counts) / len(chapter_counts) if chapter_counts else 0
        
        return {
            'total': sum(self.word_counts.values()),
            'by_act': dict(by_act),
            'by_chapter': dict(by_chapter),
            'by_scene': self.word_counts,
            'average_scene': avg_scene,
            'average_chapter': avg_chapter
        }
    
    def get_writing_progress_stats(self):
        """
        Calculate writing progress over time.
        
        Returns:
            dict: Writing progress statistics
        """
        if not self.word_count_history:
            return {
                'by_date': {},
                'cumulative': [],
                'writing_sessions': []
            }
        
        # Aggregate word counts by date
        daily_counts = defaultdict(int)
        for entry in self.word_count_history:
            daily_counts[entry['date']] += entry['word_count']
        
        # Generate cumulative count data
        dates = sorted(daily_counts.keys())
        cumulative = []
        running_total = 0
        
        for date in dates:
            running_total += daily_counts[date]
            cumulative.append({
                'date': date,
                'count': running_total
            })
        
        # Identify writing sessions
        # (timestamps with word count changes)
        sessions = []
        total_words = 0
        
        # Sort history by date and time
        sorted_history = sorted(
            self.word_count_history,
            key=lambda x: datetime.datetime.strptime(f"{x['date']} {x['time']}", '%Y-%m-%d %H:%M:%S')
        )
        
        for entry in sorted_history:
            words_added = entry['word_count'] - total_words if entry['word_count'] > total_words else 0
            if words_added > 0:
                sessions.append({
                    'date': entry['date'],
                    'time': entry['time'],
                    'words_added': words_added,
                    'scene': f"{entry['act']}-{entry['chapter']}-{entry['scene']}"
                })
                total_words = entry['word_count']
        
        return {
            'by_date': dict(daily_counts),
            'cumulative': cumulative,
            'writing_sessions': sessions
        }
    
    def get_character_stats(self):
        """
        Get statistics about character appearances and usage.
        
        Returns:
            dict: Character statistics
        """
        if not self.character_mentions:
            return {
                'appearances': {},
                'most_frequent': [],
                'scene_presence': {}
            }
        
        # Calculate total appearances
        appearances = {}
        for char_name, mentions in self.character_mentions.items():
            appearances[char_name] = sum(mention['count'] for mention in mentions)
        
        # Find most frequent characters
        most_frequent = sorted(
            appearances.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Calculate which characters appear in which scenes
        scene_presence = defaultdict(list)
        for char_name, mentions in self.character_mentions.items():
            for mention in mentions:
                scene_id = mention['scene_id']
                if char_name not in scene_presence[scene_id]:
                    scene_presence[scene_id].append(char_name)
        
        return {
            'appearances': appearances,
            'most_frequent': most_frequent,
            'scene_presence': dict(scene_presence)
        }
    
    def get_location_stats(self):
        """
        Get statistics about location usage.
        
        Returns:
            dict: Location statistics
        """
        if not self.location_mentions:
            return {
                'appearances': {},
                'most_frequent': []
            }
        
        # Calculate total appearances
        appearances = {}
        for loc_name, mentions in self.location_mentions.items():
            appearances[loc_name] = sum(mention['count'] for mention in mentions)
        
        # Find most frequent locations
        most_frequent = sorted(
            appearances.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return {
            'appearances': appearances,
            'most_frequent': most_frequent
        }
    
    def get_text_quality_stats(self):
        """
        Aggregate text quality metrics from analysis results.
        
        Returns:
            dict: Text quality statistics
        """
        if not self.analysis_results:
            return {
                'readability': {
                    'average': 0,
                    'by_scene': {}
                },
                'issues': {
                    'filter_words': 0,
                    'telling_not_showing': 0,
                    'passive_voice': 0,
                    'weak_verbs': 0,
                    'pronoun_clarity': 0
                },
                'dialogue_ratio': {
                    'average': 0,
                    'by_scene': {}
                }
            }
        
        # Initialize aggregates
        readability_scores = {}
        dialogue_ratios = {}
        total_issues = {
            'filter_words': 0,
            'telling_not_showing': 0,
            'passive_voice': 0,
            'weak_verbs': 0,
            'pronoun_clarity': 0
        }
        
        # Process each scene's analysis
        for scene_id, analysis in self.analysis_results.items():
            # Get readability
            sentences = analysis.get('sentence_analysis', [])
            if sentences:
                grades = [s.get('grade', 0) for s in sentences]
                readability_scores[scene_id] = sum(grades) / len(grades) if grades else 0
            
            # Count issues
            total_issues['filter_words'] += len(analysis.get('filter_words', []))
            total_issues['telling_not_showing'] += len(analysis.get('telling_not_showing', []))
            total_issues['weak_verbs'] += len(analysis.get('weak_verbs', []))
            total_issues['pronoun_clarity'] += len(analysis.get('pronoun_clarity', []))
            
            # Get dialogue ratio
            dialogue_ratio = analysis.get('dialogue_ratio', 0)
            dialogue_ratios[scene_id] = dialogue_ratio
        
        # Calculate averages
        avg_readability = sum(readability_scores.values()) / len(readability_scores) if readability_scores else 0
        avg_dialogue_ratio = sum(dialogue_ratios.values()) / len(dialogue_ratios) if dialogue_ratios else 0
        
        return {
            'readability': {
                'average': avg_readability,
                'by_scene': readability_scores
            },
            'issues': total_issues,
            'dialogue_ratio': {
                'average': avg_dialogue_ratio,
                'by_scene': dialogue_ratios
            }
        }
    
    def get_compendium_usage_stats(self):
        """
        Calculate statistics about compendium usage in the manuscript.
        
        Returns:
            dict: Compendium usage statistics
        """
        if not self.compendium_data:
            return {
                'usage_by_category': {},
                'unused_entries': {},
                'orphaned_references': []
            }
        
        usage_by_category = {}
        unused_entries = {}
        
        # Process each category in the compendium data
        for category_name, entries in self.compendium_data.items():
            used_entries = 0
            unused = []
            
            # Check if entries is a dictionary
            if isinstance(entries, dict):
                total_entries = len(entries)
                for entry_name in entries.keys():
                    is_used = False
                    if category_name.lower() == "characters":
                        is_used = entry_name in self.character_mentions
                    elif category_name.lower() == "locations":
                        is_used = entry_name in self.location_mentions
                    else:
                        for mention in self.custom_mentions.get(category_name, []):
                            if mention['entry'] == entry_name:
                                is_used = True
                                break
                    if is_used:
                        used_entries += 1
                    else:
                        unused.append(entry_name)
            # If entries is a list, iterate over its items
            elif isinstance(entries, list):
                total_entries = len(entries)
                for entry in entries:
                    # Assume the entry is a string; if it's a dict, try to get a name
                    entry_name = entry if isinstance(entry, str) else (entry.get("name", "Unknown") if isinstance(entry, dict) else "Unknown")
                    is_used = False
                    if category_name.lower() == "characters":
                        is_used = entry_name in self.character_mentions
                    elif category_name.lower() == "locations":
                        is_used = entry_name in self.location_mentions
                    else:
                        for mention in self.custom_mentions.get(category_name, []):
                            if mention['entry'] == entry_name:
                                is_used = True
                                break
                    if is_used:
                        used_entries += 1
                    else:
                        unused.append(entry_name)
            else:
                # If the type is unexpected, skip it.
                continue
            
            usage_percent = (used_entries / total_entries * 100) if total_entries > 0 else 0
            usage_by_category[category_name] = {
                'total': total_entries,
                'used': used_entries,
                'unused': total_entries - used_entries,
                'percent': usage_percent
            }
            if unused:
                unused_entries[category_name] = unused
        
        # Placeholder for orphaned references (not implemented yet)
        orphaned_references = []
        
        return {
            'usage_by_category': usage_by_category,
            'unused_entries': unused_entries,
            'orphaned_references': orphaned_references
        }

class StatisticsChart(QChartView):
    """
    Custom chart view for displaying statistics charts.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.chart = QChart()
        self.setChart(self.chart)
        self.chart.setAnimationOptions(QChart.SeriesAnimations)
        self.chart.legend().setVisible(True)
        self.chart.setTheme(QChart.ChartThemeLight)
        self.setRenderHint(QPainter.Antialiasing)
    
    def create_bar_chart(self, title, data, horizontal=False):
        """
        Create a bar chart with the given data.
        
        Args:
            title (str): Chart title
            data (dict): Dictionary of bar label -> value
            horizontal (bool): If True, create a horizontal bar chart
        """
        self.chart.setTitle(title)
        self.chart.removeAllSeries()
        
        # Create bar set and series
        bar_set = QBarSet("Value")
        
        # Sort by value in descending order
        sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
        
        # Extract labels and values
        labels = [item[0] for item in sorted_data]
        values = [item[1] for item in sorted_data]
        
        # Limit to top 10 items if more
        if len(labels) > 10:
            labels = labels[:10]
            values = values[:10]
        
        # Add data to bar set
        for value in values:
            bar_set.append(value)
        
        series = QBarSeries()
        series.append(bar_set)
        self.chart.addSeries(series)
        
        # Set up axes
        axis_x = QBarCategoryAxis()
        axis_x.append(labels)
        
        axis_y = QValueAxis()
        max_value = max(values) if values else 10
        axis_y.setRange(0, max_value * 1.1)  # Add 10% padding
        
        if horizontal:
            self.chart.setAxisY(axis_x)
            self.chart.setAxisX(axis_y)
        else:
            self.chart.setAxisX(axis_x)
            self.chart.setAxisY(axis_y)
        
        # Rotate labels for vertical bar chart
        if not horizontal:
            axis_x.setLabelsAngle(-45)
    
    def create_line_chart(self, title, data_points, x_key='date', y_key='count'):
        """
        Create a line chart with the given data points.
        
        Args:
            title (str): Chart title
            data_points (list): List of dictionaries with x and y values
            x_key (str): Dictionary key for x values
            y_key (str): Dictionary key for y values
        """
        self.chart.setTitle(title)
        self.chart.removeAllSeries()
        
        # Create line series
        series = QLineSeries()
        
        # Prepare data
        x_values = []
        max_y = 0
        
        for i, point in enumerate(data_points):
            x_values.append(point[x_key])
            series.append(i, point[y_key])
            if point[y_key] > max_y:
                max_y = point[y_key]
        
        self.chart.addSeries(series)
        
        # Set up axes
        axis_x = QBarCategoryAxis()
        axis_x.append(x_values)
        
        axis_y = QValueAxis()
        axis_y.setRange(0, max_y * 1.1)  # Add 10% padding
        
        self.chart.setAxisX(axis_x, series)
        self.chart.setAxisY(axis_y, series)
        
        # Rotate labels
        axis_x.setLabelsAngle(-45)


class StatisticsDialog(QDialog):
    def __init__(self, project_path, parent=None):
        super().__init__(parent)
        self.project_path = project_path
        self.project_name = os.path.basename(project_path)
        self.statistics = ProjectStatistics(project_path)

        self.setWindowTitle(f"Statistics - {self.project_name}")
        # Enable minimize and maximize buttons on the dialog
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        self.resize(900, 700)
        self.init_ui()
        
        # Load data
        self.load_data()
    
    def init_ui(self):
        """Initialize the user interface."""
        import os
        from PyQt5.QtWidgets import (
            QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QLabel, 
            QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QSplitter,
            QFrame, QScrollArea, QProgressBar, QComboBox, QGridLayout, QFileDialog, QMessageBox
        )
        from PyQt5.QtCore import Qt
        
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel(f"Project Statistics: {self.project_name}")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        # Refresh button
        refresh_button = QPushButton("Refresh")
        
        # Check if the refresh.svg file exists, if not, don't set an icon
        refresh_icon_path = os.path.join("assets", "icons", "refresh.svg")
        if os.path.exists(refresh_icon_path):
            refresh_button.setIcon(ThemeManager.get_tinted_icon(refresh_icon_path))
        else:
            print(f"Warning: Icon file not found: {refresh_icon_path}")
        
        refresh_button.clicked.connect(self.load_data)
        header_layout.addWidget(refresh_button, alignment=Qt.AlignRight)
        
        layout.addLayout(header_layout)
        
        # Create tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Create tabs
        self.create_overview_tab()
        self.create_word_count_tab()
        self.create_characters_tab()
        self.create_locations_tab()
        self.create_text_quality_tab()
        self.create_compendium_tab()
        
        # Create button box
        button_layout = QHBoxLayout()
        export_button = QPushButton("Export Report")
        
        # Check if the download.svg file exists, if not, don't set an icon
        download_icon_path = os.path.join("assets", "icons", "download.svg")
        if os.path.exists(download_icon_path):
            export_button.setIcon(ThemeManager.get_tinted_icon(download_icon_path))
        else:
            print(f"Warning: Icon file not found: {download_icon_path}")
        
        export_button.clicked.connect(self.export_report)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        
        button_layout.addWidget(export_button)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
    
    def create_overview_tab(self):
        """Create the overview tab with summary statistics."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Placeholder widgets for stats
        self.overview_stats_layout = QGridLayout()
        
        # Word count stat
        word_count_label = QLabel("Total Word Count")
        word_count_label.setStyleSheet("font-weight: bold;")
        self.word_count_value = QLabel("Loading...")
        self.word_count_value.setStyleSheet("font-size: 24px;")
        self.overview_stats_layout.addWidget(word_count_label, 0, 0)
        self.overview_stats_layout.addWidget(self.word_count_value, 1, 0)
        
        # Scene count stat
        scene_count_label = QLabel("Total Scenes")
        scene_count_label.setStyleSheet("font-weight: bold;")
        self.scene_count_value = QLabel("Loading...")
        self.scene_count_value.setStyleSheet("font-size: 24px;")
        self.overview_stats_layout.addWidget(scene_count_label, 0, 1)
        self.overview_stats_layout.addWidget(self.scene_count_value, 1, 1)
        
        # Reading time stat
        reading_time_label = QLabel("Estimated Reading Time")
        reading_time_label.setStyleSheet("font-weight: bold;")
        self.reading_time_value = QLabel("Loading...")
        self.reading_time_value.setStyleSheet("font-size: 24px;")
        self.overview_stats_layout.addWidget(reading_time_label, 0, 2)
        self.overview_stats_layout.addWidget(self.reading_time_value, 1, 2)
        
        # Character count stat
        character_count_label = QLabel("Character Count")
        character_count_label.setStyleSheet("font-weight: bold;")
        self.character_count_value = QLabel("Loading...")
        self.character_count_value.setStyleSheet("font-size: 24px;")
        self.overview_stats_layout.addWidget(character_count_label, 2, 0)
        self.overview_stats_layout.addWidget(self.character_count_value, 3, 0)
        
        # Location count stat
        location_count_label = QLabel("Location Count")
        location_count_label.setStyleSheet("font-weight: bold;")
        self.location_count_value = QLabel("Loading...")
        self.location_count_value.setStyleSheet("font-size: 24px;")
        self.overview_stats_layout.addWidget(location_count_label, 2, 1)
        self.overview_stats_layout.addWidget(self.location_count_value, 3, 1)
        
        # Last update stat
        last_update_label = QLabel("Last Updated")
        last_update_label.setStyleSheet("font-weight: bold;")
        self.last_update_value = QLabel("Loading...")
        self.last_update_value.setStyleSheet("font-size: 24px;")
        self.overview_stats_layout.addWidget(last_update_label, 2, 2)
        self.overview_stats_layout.addWidget(self.last_update_value, 3, 2)
        
        layout.addLayout(self.overview_stats_layout)
        
        # Progress chart
        self.progress_chart = StatisticsChart()
        layout.addWidget(self.progress_chart)
        
        # Recent writing sessions
        sessions_label = QLabel("Recent Writing Sessions")
        sessions_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(sessions_label)
        
        self.sessions_table = QTableWidget()
        self.sessions_table.setColumnCount(4)
        self.sessions_table.setHorizontalHeaderLabels(["Date", "Time", "Words Added", "Scene"])
        self.sessions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.sessions_table)
        
        self.tabs.addTab(tab, "Overview")
    
    def create_word_count_tab(self):
        """Create the word count tab with detailed word count statistics."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Word count by structure
        structure_label = QLabel("Word Count by Structure")
        structure_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(structure_label)
        
        # Create a splitter for charts
        charts_splitter = QSplitter(Qt.Horizontal)
        
        # Acts chart
        self.acts_chart = StatisticsChart()
        charts_splitter.addWidget(self.acts_chart)
        
        # Chapters chart
        self.chapters_chart = StatisticsChart()
        charts_splitter.addWidget(self.chapters_chart)
        
        layout.addWidget(charts_splitter)
        
        # Scenes table
        scenes_label = QLabel("Word Count by Scene")
        scenes_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(scenes_label)
        
        self.scenes_table = QTableWidget()
        self.scenes_table.setColumnCount(5)
        self.scenes_table.setHorizontalHeaderLabels(["Act", "Chapter", "Scene", "Word Count", "Last Updated"])
        self.scenes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.scenes_table)
        
        self.tabs.addTab(tab, "Word Count")
    
    def create_characters_tab(self):
        """Create the characters tab with character statistics."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Create a splitter
        splitter = QSplitter(Qt.Vertical)
        
        # Top panel - Character mentions chart
        top_panel = QWidget()
        top_layout = QVBoxLayout(top_panel)
        
        char_chart_label = QLabel("Character Mentions")
        char_chart_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        top_layout.addWidget(char_chart_label)
        
        self.character_chart = StatisticsChart()
        top_layout.addWidget(self.character_chart)
        
        splitter.addWidget(top_panel)
        
        # Bottom panel - Character appearances table
        bottom_panel = QWidget()
        bottom_layout = QVBoxLayout(bottom_panel)
        
        char_table_label = QLabel("Character Appearances by Scene")
        char_table_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        bottom_layout.addWidget(char_table_label)
        
        self.character_table = QTableWidget()
        self.character_table.setColumnCount(4)
        self.character_table.setHorizontalHeaderLabels(["Character", "Total Mentions", "Scenes", "In Compendium"])
        self.character_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        bottom_layout.addWidget(self.character_table)
        
        splitter.addWidget(bottom_panel)
        layout.addWidget(splitter)
        
        self.tabs.addTab(tab, "Characters")
    
    def create_locations_tab(self):
        """Create the locations tab with location statistics."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Location mentions chart
        loc_chart_label = QLabel("Location Mentions")
        loc_chart_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(loc_chart_label)
        
        self.location_chart = StatisticsChart()
        layout.addWidget(self.location_chart)
        
        # Location appearances table
        loc_table_label = QLabel("Location Appearances")
        loc_table_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(loc_table_label)
        
        self.location_table = QTableWidget()
        self.location_table.setColumnCount(3)
        self.location_table.setHorizontalHeaderLabels(["Location", "Total Mentions", "Scenes"])
        self.location_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.location_table)
        
        self.tabs.addTab(tab, "Locations")
    
    def create_text_quality_tab(self):
        """Create the text quality tab with text analysis statistics."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Quality metrics overview
        metrics_label = QLabel("Text Quality Metrics")
        metrics_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(metrics_label)
        
        metrics_grid = QGridLayout()
        
        # Readability score
        readability_label = QLabel("Average Readability Score:")
        self.readability_value = QLabel("Loading...")
        metrics_grid.addWidget(readability_label, 0, 0)
        metrics_grid.addWidget(self.readability_value, 0, 1)
        
        # Dialogue ratio
        dialogue_label = QLabel("Average Dialogue Ratio:")
        self.dialogue_value = QLabel("Loading...")
        metrics_grid.addWidget(dialogue_label, 1, 0)
        metrics_grid.addWidget(self.dialogue_value, 1, 1)
        
        layout.addLayout(metrics_grid)
        
        # Issues summary
        issues_label = QLabel("Writing Issues")
        issues_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(issues_label)
        
        self.issues_table = QTableWidget()
        self.issues_table.setColumnCount(3)
        self.issues_table.setHorizontalHeaderLabels(["Issue Type", "Count", "Per 1000 Words"])
        self.issues_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.issues_table)
        
        # Scene quality details
        scene_quality_label = QLabel("Scene Quality Analysis")
        scene_quality_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(scene_quality_label)
        
        self.scene_quality_table = QTableWidget()
        self.scene_quality_table.setColumnCount(5)
        self.scene_quality_table.setHorizontalHeaderLabels([
            "Scene", "Readability Score", "Dialogue %", "Issue Count", "Notes"
        ])
        self.scene_quality_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.scene_quality_table)
        
        self.tabs.addTab(tab, "Text Quality")
    
    def create_compendium_tab(self):
        """Create the compendium tab with compendium usage statistics."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Compendium usage overview
        usage_label = QLabel("Compendium Usage")
        usage_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(usage_label)
        
        # Usage chart
        self.compendium_chart = StatisticsChart()
        layout.addWidget(self.compendium_chart)
        
        # Category usage table
        self.compendium_table = QTableWidget()
        self.compendium_table.setColumnCount(4)
        self.compendium_table.setHorizontalHeaderLabels(["Category", "Total Entries", "Used in Story", "Usage %"])
        self.compendium_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.compendium_table)
        
        # Unused entries
        unused_label = QLabel("Unused Compendium Entries")
        unused_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(unused_label)
        
        self.unused_table = QTableWidget()
        self.unused_table.setColumnCount(2)
        self.unused_table.setHorizontalHeaderLabels(["Category", "Unused Entries"])
        self.unused_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.unused_table)
        
        # Potential orphaned references
        orphaned_label = QLabel("Potential Orphaned References")
        orphaned_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(orphaned_label)
        
        self.orphaned_table = QTableWidget()
        self.orphaned_table.setColumnCount(4)
        self.orphaned_table.setHorizontalHeaderLabels(["Reference", "Occurrences", "Category", "Scenes"])
        self.orphaned_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.orphaned_table)
        
        self.tabs.addTab(tab, "Compendium")
    
    def load_data(self):
        """Load project data and update the UI."""
        # Load statistics data using the ProjectStatistics instance
        success = self.statistics.load_data()
        if not success:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Load Error", "Failed to load project statistics.")
            return
        
        # Update UI with loaded data
        self.update_overview_tab()
        self.update_word_count_tab()
        self.update_characters_tab()
        self.update_locations_tab()
        self.update_text_quality_tab()
        self.update_compendium_tab()
    
    def update_overview_tab(self):
        """Update the overview tab with current statistics."""
        # Get word count stats
        word_stats = self.statistics.get_word_count_stats()
        total_words = word_stats['total']
        
        # Get scene count
        scene_count = len(self.statistics.scene_contents)
        
        # Calculate reading time (assuming 250 words per minute)
        reading_minutes = total_words / 250
        reading_hours = int(reading_minutes / 60)
        reading_mins = int(reading_minutes % 60)
        reading_time = f"{reading_hours}h {reading_mins}m"
        
        # Get character count
        character_count = len(self.statistics.character_mentions)
        
        # Get location count
        location_count = len(self.statistics.location_mentions)
        
        # Get last update time
        last_update = "Never"
        if self.statistics.word_count_history:
            last_entry = self.statistics.word_count_history[-1]
            last_update = f"{last_entry['date']} {last_entry['time']}"
        
        # Update UI elements
        self.word_count_value.setText(f"{total_words:,}")
        self.scene_count_value.setText(f"{scene_count}")
        self.reading_time_value.setText(reading_time)
        self.character_count_value.setText(f"{character_count}")
        self.location_count_value.setText(f"{location_count}")
        self.last_update_value.setText(last_update)
        
        # Update progress chart
        progress_data = self.statistics.get_writing_progress_stats()
        if progress_data['cumulative']:
            self.progress_chart.create_line_chart(
                "Writing Progress Over Time",
                progress_data['cumulative']
            )
        
        # Update sessions table
        sessions = progress_data['writing_sessions']
        self.sessions_table.setRowCount(min(len(sessions), 10))  # Show only the last 10 sessions
        
        for i, session in enumerate(sessions[-10:]):
            self.sessions_table.setItem(i, 0, QTableWidgetItem(session['date']))
            self.sessions_table.setItem(i, 1, QTableWidgetItem(session['time']))
            self.sessions_table.setItem(i, 2, QTableWidgetItem(f"{session['words_added']:,}"))
            self.sessions_table.setItem(i, 3, QTableWidgetItem(session['scene']))
    
    def update_word_count_tab(self):
        """Update the word count tab with current statistics."""
        # Get word count stats
        word_stats = self.statistics.get_word_count_stats()
        
        # Update acts chart
        self.acts_chart.create_bar_chart(
            "Word Count by Act",
            word_stats['by_act']
        )
        
        # Update chapters chart
        self.chapters_chart.create_bar_chart(
            "Word Count by Chapter",
            word_stats['by_chapter']
        )
        
        # Update scenes table
        scene_count = len(self.statistics.scene_metadata)
        self.scenes_table.setRowCount(scene_count)
        
        row = 0
        for scene_id, metadata in self.statistics.scene_metadata.items():
            word_count = word_stats['by_scene'].get(scene_id, 0)
            timestamp = metadata.get('timestamp', '')
            formatted_date = ""
            
            if timestamp:
                try:
                    date_obj = datetime.datetime.strptime(timestamp, '%Y%m%d%H%M%S')
                    formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
                except ValueError:
                    formatted_date = timestamp
            
            self.scenes_table.setItem(row, 0, QTableWidgetItem(metadata.get('act', 'Unknown')))
            self.scenes_table.setItem(row, 1, QTableWidgetItem(metadata.get('chapter', 'Unknown')))
            self.scenes_table.setItem(row, 2, QTableWidgetItem(metadata.get('scene', 'Unknown')))
            self.scenes_table.setItem(row, 3, QTableWidgetItem(f"{word_count:,}"))
            self.scenes_table.setItem(row, 4, QTableWidgetItem(formatted_date))
            row += 1
        
        # Sort by act, chapter, scene
        self.scenes_table.sortItems(0)
    
    def update_characters_tab(self):
        """Update the characters tab with current statistics."""
        try:
            # Get character stats
            char_stats = self.statistics.get_character_stats()
            
            # Update character chart
            self.character_chart.create_bar_chart(
                "Most Mentioned Characters",
                char_stats['appearances'],
                horizontal=True
            )
            
            # Update character table
            char_count = len(char_stats['appearances'])
            self.character_table.setRowCount(char_count)
            
            row = 0
            for char_name, mentions in char_stats['appearances'].items():
                # Find scenes where character appears
                scenes = []
                for scene_id, chars in char_stats['scene_presence'].items():
                    if char_name in chars:
                        metadata = self.statistics.scene_metadata.get(scene_id, {})
                        scene_label = f"{metadata.get('act', '')}-{metadata.get('chapter', '')}-{metadata.get('scene', '')}"
                        scenes.append(scene_label)
                
                # Check if character is in compendium
                in_compendium = "✓" if char_name in self.statistics.compendium_data.get("characters", {}) else "✗"
                
                self.character_table.setItem(row, 0, QTableWidgetItem(char_name))
                self.character_table.setItem(row, 1, QTableWidgetItem(f"{mentions:,}"))
                self.character_table.setItem(row, 2, QTableWidgetItem(", ".join(scenes[:3]) + ("..." if len(scenes) > 3 else "")))
                self.character_table.setItem(row, 3, QTableWidgetItem(in_compendium))
                row += 1
            
            # Sort by mentions
            self.character_table.sortItems(1, Qt.DescendingOrder)
        except Exception as e:
            print(f"Error updating characters tab: {e}")
            QMessageBox.warning(self, "Error", f"Could not update characters tab: {e}")
    
    def update_locations_tab(self):
        """Update the locations tab with current statistics."""
        # Get location stats
        loc_stats = self.statistics.get_location_stats()
        
        # Update location chart
        self.location_chart.create_bar_chart(
            "Most Mentioned Locations",
            loc_stats['appearances']
        )
        
        # Update location table
        loc_count = len(loc_stats['appearances'])
        self.location_table.setRowCount(loc_count)
        
        row = 0
        for loc_name, mentions in loc_stats['appearances'].items():
            # Find scenes where location appears
            scenes = []
            for mention_data in self.statistics.location_mentions.get(loc_name, []):
                scene_id = mention_data['scene_id']
                metadata = self.statistics.scene_metadata.get(scene_id, {})
                scene_label = f"{metadata.get('act', '')}-{metadata.get('chapter', '')}-{metadata.get('scene', '')}"
                scenes.append(scene_label)
            
            self.location_table.setItem(row, 0, QTableWidgetItem(loc_name))
            self.location_table.setItem(row, 1, QTableWidgetItem(f"{mentions:,}"))
            self.location_table.setItem(row, 2, QTableWidgetItem(", ".join(scenes[:3]) + ("..." if len(scenes) > 3 else "")))
            row += 1
        
        # Sort by mentions
        self.location_table.sortItems(1, Qt.DescendingOrder)
    
    def update_text_quality_tab(self):
        """Update the text quality tab with current statistics."""
        # Get text quality stats
        quality_stats = self.statistics.get_text_quality_stats()
        
        # Update readability and dialogue scores
        self.readability_value.setText(f"{quality_stats['readability']['average']:.1f} (Grade level)")
        self.dialogue_value.setText(f"{quality_stats['dialogue_ratio']['average'] * 100:.1f}%")
        
        # Update issues table
        issues = quality_stats['issues']
        self.issues_table.setRowCount(len(issues))
        
        row = 0
        total_words = self.statistics.get_word_count_stats()['total']
        for issue_type, count in issues.items():
            # Format issue type name
            display_name = " ".join(word.capitalize() for word in issue_type.split('_'))
            
            # Calculate per 1000 words
            per_1000 = (count / total_words * 1000) if total_words > 0 else 0
            
            self.issues_table.setItem(row, 0, QTableWidgetItem(display_name))
            self.issues_table.setItem(row, 1, QTableWidgetItem(f"{count:,}"))
            self.issues_table.setItem(row, 2, QTableWidgetItem(f"{per_1000:.1f}"))
            row += 1
        
        # Update scene quality table
        scene_count = len(self.statistics.scene_metadata)
        self.scene_quality_table.setRowCount(scene_count)
        
        row = 0
        for scene_id, metadata in self.statistics.scene_metadata.items():
            # Get scene data
            scene_label = f"{metadata.get('act', '')}-{metadata.get('chapter', '')}-{metadata.get('scene', '')}"
            readability = quality_stats['readability']['by_scene'].get(scene_id, 0)
            dialogue_ratio = quality_stats['dialogue_ratio']['by_scene'].get(scene_id, 0)
            
            # Count issues in this scene
            issue_count = 0
            if scene_id in self.statistics.analysis_results:
                analysis = self.statistics.analysis_results[scene_id]
                issue_count += len(analysis.get('filter_words', []))
                issue_count += len(analysis.get('telling_not_showing', []))
                issue_count += len(analysis.get('weak_verbs', []))
                issue_count += len(analysis.get('pronoun_clarity', []))
            
            # Generate notes
            notes = []
            if readability > 10:
                notes.append("High readability score")
            if dialogue_ratio > 0.7:
                notes.append("Dialogue-heavy")
            elif dialogue_ratio < 0.1:
                notes.append("Little dialogue")
            
            self.scene_quality_table.setItem(row, 0, QTableWidgetItem(scene_label))
            self.scene_quality_table.setItem(row, 1, QTableWidgetItem(f"{readability:.1f}"))
            self.scene_quality_table.setItem(row, 2, QTableWidgetItem(f"{dialogue_ratio * 100:.1f}%"))
            self.scene_quality_table.setItem(row, 3, QTableWidgetItem(f"{issue_count:,}"))
            self.scene_quality_table.setItem(row, 4, QTableWidgetItem(", ".join(notes)))
            row += 1
    
    def update_compendium_tab(self):
        """Update the compendium tab with current statistics."""
        # Get compendium stats
        compendium_stats = self.statistics.get_compendium_usage_stats()
        
        # If no compendium data, show message
        if not compendium_stats['usage_by_category']:
            self.compendium_chart.chart.setTitle("No Compendium Data Available")
            self.compendium_table.setRowCount(0)
            self.unused_table.setRowCount(0)
            self.orphaned_table.setRowCount(0)
            return
        
        # Update compendium chart - show usage percentages
        usage_percentages = {
            category: data['percent']
            for category, data in compendium_stats['usage_by_category'].items()
        }
        self.compendium_chart.create_bar_chart(
            "Compendium Usage Percentage by Category",
            usage_percentages
        )
        
        # Update category usage table
        category_count = len(compendium_stats['usage_by_category'])
        self.compendium_table.setRowCount(category_count)
        
        row = 0
        for category, data in compendium_stats['usage_by_category'].items():
            self.compendium_table.setItem(row, 0, QTableWidgetItem(category))
            self.compendium_table.setItem(row, 1, QTableWidgetItem(f"{data['total']:,}"))
            self.compendium_table.setItem(row, 2, QTableWidgetItem(f"{data['used']:,}"))
            self.compendium_table.setItem(row, 3, QTableWidgetItem(f"{data['percent']:.1f}%"))
            row += 1
        
        # Update unused entries table
        unused_count = len(compendium_stats['unused_entries'])
        self.unused_table.setRowCount(unused_count)
        
        row = 0
        for category, entries in compendium_stats['unused_entries'].items():
            self.unused_table.setItem(row, 0, QTableWidgetItem(category))
            self.unused_table.setItem(row, 1, QTableWidgetItem(", ".join(entries)))
            row += 1
        
        # Update orphaned references table
        orphaned_count = len(compendium_stats['orphaned_references'])
        self.orphaned_table.setRowCount(orphaned_count)
        
        # Not yet implemented - placeholder for future feature
        if orphaned_count == 0:
            self.orphaned_table.setRowCount(1)
            self.orphaned_table.setSpan(0, 0, 1, 4)
            self.orphaned_table.setItem(0, 0, QTableWidgetItem("Orphaned references detection will be available in a future update"))
    
    def export_report(self):
        """Export statistics as an HTML report."""
        # Get export path
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        
        file_path, unused = QFileDialog.getSaveFileName(
            self, "Export Statistics Report", "", "HTML Files (*.html)"
        )
        
        if not file_path:
            return
        
        # Add .html extension if not provided
        if not file_path.endswith('.html'):
            file_path += '.html'
        
        # Generate HTML report
        try:
            self._generate_html_report(file_path)
            QMessageBox.information(self, "Export Successful", f"Statistics report exported to {file_path}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", f"Failed to export report: {str(e)}")
    
    def _generate_html_report(self, file_path):
        """Generate an HTML report with all statistics."""
        import datetime
        
        # Get all stats
        word_stats = self.statistics.get_word_count_stats()
        character_stats = self.statistics.get_character_stats()
        location_stats = self.statistics.get_location_stats()
        quality_stats = self.statistics.get_text_quality_stats()
        compendium_stats = self.statistics.get_compendium_usage_stats()
        progress_stats = self.statistics.get_writing_progress_stats()
        
        # Generate HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Statistics Report - {self.project_name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2, h3 {{ color: #444; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .stat-box {{ display: inline-block; width: 200px; margin: 10px; padding: 15px; 
                            text-align: center; background-color: #f5f5f5; border-radius: 5px; }}
                .stat-value {{ font-size: 24px; font-weight: bold; margin: 10px 0; }}
                .stat-label {{ font-size: 14px; color: #666; }}
            </style>
        </head>
        <body>
            <h1>Project Statistics: {self.project_name}</h1>
            <p>Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <h2>Overview</h2>
            <div>
                <div class="stat-box">
                    <div class="stat-label">Total Words</div>
                    <div class="stat-value">{word_stats['total']:,}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Total Scenes</div>
                    <div class="stat-value">{len(self.statistics.scene_contents)}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Reading Time</div>
                    <div class="stat-value">{int(word_stats['total'] / 250 / 60)}h {int(word_stats['total'] / 250 % 60)}m</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Characters</div>
                    <div class="stat-value">{len(character_stats['appearances'])}</div></div>
                <div class="stat-box">
                    <div class="stat-label">Locations</div>
                    <div class="stat-value">{len(location_stats['appearances'])}</div>
                </div>
            </div>
            
            <h2>Word Count</h2>
            <h3>By Act</h3>
            <table>
                <tr><th>Act</th><th>Word Count</th></tr>
        """
        
        # Add act word counts
        for act, count in sorted(word_stats['by_act'].items()):
            html += f"<tr><td>{act}</td><td>{count:,}</td></tr>\n"
        
        html += """
            </table>
            
            <h3>By Chapter</h3>
            <table>
                <tr><th>Chapter</th><th>Word Count</th></tr>
        """
        
        # Add chapter word counts
        for chapter, count in sorted(word_stats['by_chapter'].items()):
            html += f"<tr><td>{chapter}</td><td>{count:,}</td></tr>\n"
        
        html += """
            </table>
            
            <h3>By Scene</h3>
            <table>
                <tr><th>Scene</th><th>Word Count</th><th>Last Updated</th></tr>
        """
        
        # Add scene word counts
        for scene_id, count in sorted(word_stats['by_scene'].items()):
            metadata = self.statistics.scene_metadata.get(scene_id, {})
            timestamp = metadata.get('timestamp', '')
            formatted_date = ""
            
            if timestamp:
                try:
                    if isinstance(timestamp, str):
                        date_obj = datetime.datetime.strptime(timestamp, '%Y%m%d%H%M%S')
                        formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
                    else:
                        # Assume it's a timestamp
                        formatted_date = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
                except:
                    formatted_date = str(timestamp)
            
            scene_label = f"{metadata.get('act', '')}-{metadata.get('chapter', '')}-{metadata.get('scene', '')}"
            html += f"<tr><td>{scene_label}</td><td>{count:,}</td><td>{formatted_date}</td></tr>\n"
        
        html += """
            </table>
            
            <h2>Characters</h2>
            <table>
                <tr><th>Character</th><th>Mentions</th><th>Scenes</th></tr>
        """
        
        # Add character stats
        for char_name, mentions in sorted(character_stats['appearances'].items(), key=lambda x: x[1], reverse=True):
            # Find scenes where character appears
            scenes = []
            for scene_id, chars in character_stats['scene_presence'].items():
                if char_name in chars:
                    metadata = self.statistics.scene_metadata.get(scene_id, {})
                    scene_label = f"{metadata.get('act', '')}-{metadata.get('chapter', '')}-{metadata.get('scene', '')}"
                    scenes.append(scene_label)
            
            html += f"<tr><td>{char_name}</td><td>{mentions:,}</td><td>{', '.join(scenes)}</td></tr>\n"
        
        html += """
            </table>
            
            <h2>Locations</h2>
            <table>
                <tr><th>Location</th><th>Mentions</th><th>Scenes</th></tr>
        """
        
        # Add location stats
        for loc_name, mentions in sorted(location_stats['appearances'].items(), key=lambda x: x[1], reverse=True):
            # Find scenes where location appears
            scenes = []
            for mention_data in self.statistics.location_mentions.get(loc_name, []):
                scene_id = mention_data['scene_id']
                metadata = self.statistics.scene_metadata.get(scene_id, {})
                scene_label = f"{metadata.get('act', '')}-{metadata.get('chapter', '')}-{metadata.get('scene', '')}"
                scenes.append(scene_label)
            
            html += f"<tr><td>{loc_name}</td><td>{mentions:,}</td><td>{', '.join(scenes)}</td></tr>\n"
        
        html += """
            </table>
        </body>
        </html>
        """
        
        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html)


def show_statistics(project_path):
    """
    Show the statistics dialog for a project.
    
    Args:
        project_path (str): Path to the project directory
    """
    from PyQt5.QtWidgets import QApplication, QMessageBox
    import sys
    
    print(f"Opening statistics for project: {project_path}")
    print(f"Absolute path: {os.path.abspath(project_path)}")
    
    if not os.path.exists(project_path):
        error_msg = f"Project path does not exist: {project_path}"
        print(f"ERROR: {error_msg}")
        QMessageBox.critical(None, "Project Not Found", error_msg)
        return
    
    # If we're running standalone, create an application
    app = None
    if not QApplication.instance():
        app = QApplication(sys.argv)
    
    try:
        # Create and show the dialog
        dialog = StatisticsDialog(project_path)
        dialog.exec_()
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR: {error_details}")
        QMessageBox.critical(None, "Statistics Error", 
                           f"Error loading statistics: {str(e)}\n\n"
                           f"Details:\n{error_details}")
    
    # Exit if we created the application
    if app:
        sys.exit(app.exec_())


if __name__ == "__main__":
    # For testing purposes
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # If a project path is provided as argument, use it
    if len(sys.argv) > 1:
        project_path = sys.argv[1]
    else:
        # Default test project path
        project_path = "./MyFirstProject"
    
    dialog = StatisticsDialog(project_path)
    dialog.exec_()
    
    sys.exit(app.exec_())