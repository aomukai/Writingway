import json
import os
import re
from typing import Dict, List, Optional

class CompendiumManager:
    """Manages compendium data loading, retrieval, and reference parsing for a project."""

    def __init__(self, project_name: Optional[str] = None):
        """
        Initialize the CompendiumManager with an optional project name.

        Args:
            project_name (str, optional): The name of the project. If None, uses a global compendium file.
        """
        self.project_name = project_name

    def _sanitize(self, text: str) -> str:
        """Sanitize text by removing non-word characters."""
        return re.sub(r'\W+', '', text)

    def get_filepath(self) -> str:
        """
        Build the compendium file path based on the project name.

        Returns:
            str: Path to the compendium JSON file.
        """
        if self.project_name:
            sanitized_name = self._sanitize(self.project_name)
            return os.path.join(os.getcwd(), "Projects", sanitized_name, "compendium.json")
        return "compendium.json"

    def load_data(self) -> Dict[str, List]:
        """
        Load compendium data from the project-specific file, converting legacy formats if needed.

        Returns:
            dict: Compendium data with a 'categories' key containing a list of category objects.
        """
        filename = self.get_filepath()
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Convert legacy dict format to list of categories
                categories = data.get("categories", [])
                if isinstance(categories, dict):
                    new_categories = [{"name": cat, "entries": entries} for cat, entries in categories.items()]
                    data["categories"] = new_categories
                return data
            except Exception as e:
                print(f"Error loading compendium data from {filename}: {e}")
        return {"categories": []}
    
    def get_category(self, category: str) -> List[Dict[str, str]]:
        data = self.load_data()
        categories = data.get("categories", [])
        for cat in categories:
            if cat.get("name") == category:
                return cat.get("entries", [])
        return []

    def get_text(self, category: str, entry: str) -> str:
        """
        Retrieve the text content for a given category and entry.

        Args:
            category (str): The category name.
            entry (str): The entry name within the category.

        Returns:
            str: The content of the entry, or a placeholder if not found.
        """
        data = self.load_data()
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
        filename = self.get_filepath()
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
