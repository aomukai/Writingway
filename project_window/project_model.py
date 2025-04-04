#!/usr/bin/env python3
import os
import re
from . import project_settings_manager as psm
from settings.settings_manager import WWSettingsManager
from settings.autosave_manager import load_latest_autosave, save_scene
from .tree_manager import load_structure, save_structure, update_structure_from_tree

class ProjectModel:
    """Manages project data and persistence."""
    def __init__(self, project_name):
        self.project_name = project_name
        self.structure = load_structure(project_name)
        self.settings = self.load_settings()
        self.autosave_enabled = WWSettingsManager.get_setting("general", "enable_autosave", False)
        self.unsaved_changes = False

    def sanitize(self, text):
        """Sanitize text by removing non-alphanumeric characters."""
        return re.sub(r'\W+', '', text)

    def load_settings(self):
        """Load project settings with defaults."""
        settings = psm.load_project_settings(self.project_name)
        return {
            "global_pov": settings.get("global_pov", "Third Person Limited"),
            "global_pov_character": settings.get("global_pov_character", "Character"),
            "global_tense": settings.get("global_tense", "Present Tense")
        }

    def save_settings(self):
        """Save current settings to file."""
        psm.save_project_settings(self.project_name, self.settings)

    def update_structure(self, tree):
        """Update project structure from the tree widget."""
        self.structure = update_structure_from_tree(tree, self.project_name)
        self.save_structure()

    def save_structure(self):
        """Persist the project structure."""
        save_structure(self.project_name, self.structure)

    def load_autosave(self, hierarchy):
        """Load the latest autosave for a given hierarchy."""
        return load_latest_autosave(self.project_name, hierarchy)

    def save_scene(self, hierarchy, content):
        """Save scene content with the given hierarchy."""
        return save_scene(self.project_name, hierarchy, content)
        
    def check_provider_availability(self, provider_name):
        config = WWSettingsManager.get_llm_config(provider_name)
        return bool(config and config.get("api_key"))