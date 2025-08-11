import json
import os

from settings.settings_manager import WWSettingsManager

def get_prompt_categories():
    return ["Workshop", "Summary", "Prose", "Rewrite", "Judge"]

def get_workshop_prompts(): # backward compatibility for workshop
    """
    Loads workshop prompts from a global prompts file.
    The file is now named 'prompts.json', regardless of the project.
    Returns a list of prompt objects from the "Workshop" category.
    If the file is missing or fails to load, returns a dummy prompt.
    """
    return load_prompts("Workshop")

def load_project_options(project_name):
    """Load project options to inject dynamic values into default prompts."""
    options = {}
    PROJECT_SETTINGS_FILE = "project_settings.json"
    filepath = WWSettingsManager.get_project_path(file=PROJECT_SETTINGS_FILE)
    if not os.path.exists(filepath):
        oldpath = os.path.join(os.getcwd(), PROJECT_SETTINGS_FILE) # backward compatibility
        if (os.path.exists(oldpath)):
            os.rename(oldpath, filepath)

    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                all_settings = json.load(f)
            options = all_settings.get(project_name, {})
        except Exception as e:
            print("Error loading project options:", e)
    return options

def get_default_prompt(style:str):
    default_prompts = {
        "Prose": _("You are collaborating with the author to write a scene. Write the scene in {pov} point of view, from the perspective of {pov_character}, and in {tense}."),
        "Summary": _("Summarize the following chapter for use in a story prompt, covering Goal, Key Events, Character Dev, Info Revealed, Emotional Arc, and Plot Setup. Be conscientious of token usage."),
        "Rewrite": _("Rewrite the passage for clarity."),
        "Workshop": _("I need your help with my project. Please provide creative brainstorming and ideas."),
        "Judge": _("Rank and evaluate the following responses. Provide a brief explanation for your ranking and highlight the strengths and weaknesses of each response."),
    }
    default_config = {
        "name": _("Default {} Prompt").format(style),
        "text": default_prompts.get(style, ""),
        "max_tokens": 2000,
        "temperature": 0.7,
        "default": True
    }
    return default_config

def load_prompts(style:str):
    prompt = None
    try:
        prompt = _load_prompt_style(style)
    except Exception as e:
        print(f"Error loading {style} prompts:", e)
    
    if not style:
        return prompt # empty dictionary means no json file found
    return prompt or [get_default_prompt(style)]


def _load_prompt_style(style:str):
    """
    style: Prose, Summary, Rewrite, or Workshop. None returns the dict of styles
    Returns a list of dictionary entries for each prompt definition in the given style
    """
    filepath = WWSettingsManager.get_project_path(file="prompts.json")
    data = {}
    if not os.path.exists(filepath):
        oldpath = "prompts.json" # backward compatibility
        if os.path.exists(oldpath):
            os.rename(oldpath, filepath)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if style:
            return data.get(style, [])
    return data