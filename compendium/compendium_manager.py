from typing import Callable, Dict, List, Optional, Any
from uuid import uuid4
import json
import os
import re
from settings.settings_manager import WWSettingsManager

class CompendiumEventBus:
    _instance = None

    def __init__(self):
        self.updated_listeners: List[Callable[[str], None]] = []

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def add_updated_listener(self, callback: Callable[[str], None]):
        self.updated_listeners.append(callback)

    def notify_updated(self, project_name: str):
        for callback in self.updated_listeners:
            callback(project_name)


class CompendiumManager:
    """Manages compendium data loading, retrieval, and reference parsing for a project."""

    def __init__(self, project_name: Optional[str] = None, event_bus: Optional[CompendiumEventBus] = None):
        """
        Initialize the CompendiumManager with an optional project name.

        Args:
            project_name (str, optional): The name of the project. If None, uses a global compendium file.
        """
        self.project_name = project_name
        self.event_bus = event_bus
        self._filepath = self._get_filepath()
        self._ensure_file_exists()

    def _get_filepath(self) -> str:
        """
        Build the compendium file path based on the project name.

        Returns:
            str: Path to the compendium JSON file.
        """
        if self.project_name:
            return WWSettingsManager.get_project_relpath(self.project_name, "compendium.json")
        return os.path.join(os.getcwd(), "compendium.json")

    def _ensure_file_exists(self) -> None:
        """Ensure the compendium file exists, creating a default one if necessary."""
        if not os.path.exists(self._filepath):
            os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
            default_data = {
                "categories": [{"name": "Characters", "entries": []}],
                "extensions": {"entries": {}}
            }
            self._save_data(default_data)

    def _load_data(self) -> Dict[str, Any]:
        """
        Load compendium data from the project-specific file, converting legacy formats if needed.

        Returns:
            dict: Compendium data with a 'categories' key containing a list of category objects.
        """
        if not os.path.exists(self._filepath):
            self._ensure_file_exists()

        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {self._filepath}: {e}. Initializing empty compendium.")
            data = {"categories": [], "extensions": {"entries": {}}}
            self._save_data(data)
        except Exception as e:
            print(f"Error loading compendium data from {self._filepath}: {e}")
            data = {"categories": [], "extensions": {"entries": {}}}
            self._save_data(data)

        # Ensure essential keys exist
        data.setdefault("categories", [])
        data.setdefault("extensions", {"entries": {}})

        # Convert legacy dict format to list of categories
        if isinstance(data["categories"], dict):
            new_categories = [
                {"name": cat, "entries": [
                    {"name": name, "content": content, "uuid": str(uuid4())}
                    for name, content in entries.items()
                ]} for cat, entries in data["categories"].items()
            ]
            data["categories"] = new_categories
            self._save_data(data)

        # Ensure UUIDs for all entries
        changed = False
        for cat in data["categories"]:
            for entry in cat.get("entries", []):
                if "uuid" not in entry:
                    entry["uuid"] = str(uuid4())
                    changed = True
                # Ensure entry name exists in extensions
                entry_name = entry.get("name")
                if entry_name and entry_name not in data["extensions"]["entries"]:
                    data["extensions"]["entries"][entry_name] = {
                        "details": "",
                        "tags": [],
                        "relationships": [],
                        "images": []
                    }
                    changed = True
        if changed:
            self._save_data(data)

        return data

    def load_data(self) -> Dict[str, Any]:
        return self._load_data()

    def _save_data(self, compendium_data: Dict[str, Any]) -> None:
        """
        Save compendium data to the file.

        Args:
            compendium_data (dict): The compendium data to save.
        """
        try:
            os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
            with open(self._filepath, "w", encoding="utf-8") as f:
                json.dump(compendium_data, f, indent=2)
            if self.event_bus:
                self.event_bus.notify_updated(self.project_name)
        except Exception as e:
            print(f"Error saving compendium data to {self._filepath}: {e}")

    def save_data(self, compendium_data: Dict[str, Any]) -> None:
        self._save_data(compendium_data)

    def get_category(self, category: str) -> List[Dict[str, str]]:
        data = self._load_data()
        categories = data.get("categories", [])
        for cat in categories:
            if cat.get("name") == category:
                return cat.get("entries", [])
        return []

    def get_characters(self) -> List[str]:
        character_dicts = self.get_category("Characters")
        characters = [d['name'] for d in character_dicts]
        characters.sort()
        return characters
    
    def get_text(self, category: str, entry: str) -> str:
        """
        Retrieve the text content for a given category and entry.

        Args:
            category (str): The category name.
            entry (str): The entry name within the category.

        Returns:
            str: The content of the entry, or a placeholder if not found.
        """
        data = self._load_data()
        categories = data.get("categories", [])
        for cat in categories:
            if cat.get("name") == category:
                for e in cat.get("entries", []):
                    if e.get("name") == entry:
                        return e.get("content", f"[No content for {entry} in category {category}]")
        return f"[No content for {entry} in category {category}]"

    def parse_references(self, message: str) -> List[str]:
        """
        Parse compendium references from a message by matching entry names.

        Args:
            message (str): The text to search for references.

        Returns:
            list: A list of entry names found in the message.
        """
        filename = self._get_filepath()
        refs = []
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    compendium = json.load(f)
                names = []
                cats = compendium.get("categories", [])
                if isinstance(cats, dict):
                    names = list(cats.keys())
                elif isinstance(cats, list):
                    for cat in cats:
                        for entry in cat.get("entries", []):
                            names.append(entry.get("name", ""))
                for name in names:
                    if name and re.search(r'\b' + re.escape(name) + r'\b', message, re.IGNORECASE):
                        refs.append(name)
            except Exception as e:
                print(f"Error parsing compendium references from {filename}: {e}")
        return refs

    def add_character(self, name, description) -> None:
        """Add a new character to the compendium.json file."""
        compendium_data = self._load_data()
        
        # Find or create Characters category
        characters_cat = None
        for cat in compendium_data.get("categories", []):
            if cat.get("name", "").lower() == "characters":
                characters_cat = cat
                break
        if not characters_cat:
            characters_cat = {"name": "Characters", "entries": []}
            compendium_data["categories"].append(characters_cat)
        
        # Check if character already exists
        for entry in characters_cat.get("entries", []):
            if entry.get("name") == name:
                entry["content"] = description
                break
        else:
            # Add new character entry
            characters_cat["entries"].append({"name": name, "content": description})
        
        # Ensure extensions section exists
        if "extensions" not in compendium_data:
            compendium_data["extensions"] = {"entries": {}}
        elif "entries" not in compendium_data["extensions"]:
            compendium_data["extensions"]["entries"] = {}
        
        # Add minimal extended data
        if name not in compendium_data["extensions"]["entries"]:
            compendium_data["extensions"]["entries"][name] = {"details": "", "tags": [], "relationships": [], "images": []}
        
        self._save_data(compendium_data)

    def upsert_data(self, compendium_data: Dict[str, Any]) -> None:
        """ Merge compendium_data with the existing compendium content. """
        existing_data = self._load_data()

        # Merge categories
        existing_categories = {cat["name"]: cat for cat in existing_data.get("categories", [])}
        new_categories = compendium_data.get("categories", [])
        for new_cat in new_categories:
            if new_cat["name"] in existing_categories:
                existing_entries = {entry["name"]: entry for entry in existing_categories[new_cat["name"]].get("entries", [])}
                for new_entry in new_cat.get("entries", []):
                    if new_entry["name"] in existing_entries:
                        existing_entries[new_entry["name"]].update(new_entry)
                    else:
                        existing_categories[new_cat["name"]]["entries"].append(new_entry)
            else:
                existing_data["categories"].append(new_cat)

        # Merge extensions
        existing_extensions = existing_data.get("extensions", {}).get("entries", {})
        new_extensions = compendium_data.get("extensions", {}).get("entries", {})
        for key, value in new_extensions.items():
            if key in existing_extensions:
                existing_extensions[key].update(value)
            else:
                existing_extensions[key] = value

        existing_data["extensions"] = {"entries": existing_extensions}

        compendium_data.update(existing_data)
        self._save_data(compendium_data)
