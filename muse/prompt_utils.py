import json
import os
from typing import Dict, List, Optional, Union, Any

from settings.settings_manager import WWSettingsManager

def get_prompt_categories() -> List[str]:
    """Return the list of supported prompt categories."""
    return ["Workshop", "Summary", "Prose", "Rewrite", "Roleplay"]

def get_default_prompt(style: str) -> Dict:
    """Return the default prompt configuration for the given style."""
    default_prompts = {
        "Prose": _("You are collaborating with the author to write a scene. Write the scene in {pov} point of view, from the perspective of {pov_character}, and in {tense}."),
        "Summary": _("Summarize the following chapter for use in a story prompt, covering Goal, Key Events, Character Dev, Info Revealed, Emotional Arc, and Plot Setup. Be conscientious of token usage."),
        "Rewrite": _("Rewrite the passage for clarity."),
        "Workshop": _("I need your help with my project. Please provide creative brainstorming and ideas."),
        "Roleplay": _("You are role-playing as the character(s) described below. Stay in character, using their voice, personality, and perspective in all responses. Creatively add details about the character where appropriate, but do not deviate from the provided description unless explicitly asked.")
    }
    return {
        "name": _("Default {} Prompt").format(style),
        "text": default_prompts.get(style, ""),
        "max_tokens": 2000,
        "temperature": 0.7,
        "default": True,
        "id": f"default_{style.lower()}"
    }

def load_prompts(style: Optional[str] = None) -> Union[Dict[str, List[Dict]], List[Dict]]:
    """Load prompts from the prompts.json file."""
    try:
        return _load_prompt_style(style)
    except Exception as e:
        print(f"Error loading {style or 'all'} prompts: {e}")
        return {} if not style else [get_default_prompt(style)]

def save_prompts(prompts_data: Dict[str, List[Dict]], prompts_file: str, backup_file: str) -> bool:
    """Save prompts to the specified file and create a backup."""
    try:
        with open(prompts_file, "w", encoding="utf-8") as f:
            json.dump(prompts_data, f, indent=4)
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(prompts_data, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving prompts: {e}")
        return False

def _load_prompt_style(style: Optional[str]) -> Union[Dict[str, List[Dict]], List[Dict]]:
    """Load prompts for a specific style or all styles from prompts.json."""
    filepath = WWSettingsManager.get_project_path(file="prompts.json")
    data = {}
    
    if not os.path.exists(filepath):
        oldpath = "prompts.json"
        if os.path.exists(oldpath):
            os.rename(oldpath, filepath)
    
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    
    if style:
        return data.get(style, [])
    return data