#!/usr/bin/env python3
import os
import time
import glob
import re

NEW_FILE_EXTENSION = ".html"  # Use HTML for new files

def sanitize(text: str) -> str:
    """Return a sanitized string suitable for file names."""
    return re.sub(r'\W+', '', text)

def build_scene_identifier(project_name: str, hierarchy: list) -> str:
    """
    Create a unique scene identifier by combining the sanitized project name
    with the sanitized hierarchy list (e.g., [Act, Chapter, Scene]).
    """
    sanitized_project = sanitize(project_name)
    sanitized_hierarchy = [sanitize(item) for item in hierarchy]
    return f"{sanitized_project}-" + "-".join(sanitized_hierarchy)

def get_project_folder(project_name: str) -> str:
    """
    Return the full path to the project folder.
    Creates the folder if it doesn't already exist.
    """
    sanitized_project = sanitize(project_name)
    project_folder = os.path.join(os.getcwd(), "Projects", sanitized_project)
    if not os.path.exists(project_folder):
        os.makedirs(project_folder)
    return project_folder

def get_latest_autosave_path(project_name: str, hierarchy: list) -> str | None:
    """
    Return the path to the most recent autosave file for a given scene.
    Supports both legacy .txt files and new .html files.
    Returns None if no autosave file exists.
    """
    scene_identifier = build_scene_identifier(project_name, hierarchy)
    project_folder = get_project_folder(project_name)
    pattern_txt = os.path.join(project_folder, f"{scene_identifier}_*.txt")
    pattern_html = os.path.join(project_folder, f"{scene_identifier}_*{NEW_FILE_EXTENSION}")
    autosave_files = glob.glob(pattern_txt) + glob.glob(pattern_html)
    if not autosave_files:
        return None
    return max(autosave_files, key=os.path.getmtime)

def load_latest_autosave(project_name: str, hierarchy: list) -> str | None:
    """
    Load the content of the most recent autosave file for a given scene.
    Returns the content if found, or None otherwise.
    """
    latest_file = get_latest_autosave_path(project_name, hierarchy)
    if not latest_file:
        return None
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error loading autosave file {latest_file}: {e}")
        return None

def cleanup_old_autosaves(project_folder: str, scene_identifier: str, max_files: int = 6) -> None:
    """
    Remove the oldest autosave files if the number of autosaves exceeds max_files.
    Searches for both .txt and .html files.
    """
    pattern_txt = os.path.join(project_folder, f"{scene_identifier}_*.txt")
    pattern_html = os.path.join(project_folder, f"{scene_identifier}_*{NEW_FILE_EXTENSION}")
    autosave_files = sorted(glob.glob(pattern_txt) + glob.glob(pattern_html), key=os.path.getmtime)
    while len(autosave_files) > max_files:
        oldest = autosave_files.pop(0)
        try:
            os.remove(oldest)
            print("Removed old autosave file:", oldest)
        except Exception as e:
            print("Error removing old autosave file:", e)

def save_scene(project_name: str, hierarchy: list, content: str, expected_project_name: str = None) -> str:
    """
    Save the scene content if it has changed since the last autosave.
    Uses the new HTML format for saving, preserving rich formatting.
    
    Parameters:
        project_name (str): The name of the project.
        hierarchy (list): List of strings representing the scene hierarchy (e.g., [Act, Chapter, Scene]).
        content (str): The scene content to save (HTML formatted).
        expected_project_name (str, optional): The project name expected by the caller for validation.
    
    Returns:
        The filepath of the new autosave file if saved, or None if no changes were detected.
    """
    # Check if the scene content has changed.
    last_content = load_latest_autosave(project_name, hierarchy)
    if last_content is not None and last_content.strip() == content.strip():
        print("No changes detected since the last autosave. Skipping autosave.")
        return None

    scene_identifier = build_scene_identifier(project_name, hierarchy)
    project_folder = get_project_folder(project_name)
    timestamp = time.strftime("%Y%m%d%H%M%S")
    filename = f"{scene_identifier}_{timestamp}{NEW_FILE_EXTENSION}"
    filepath = os.path.join(project_folder, filename)

    # Validate project directory if expected_project_name is provided
    if expected_project_name and expected_project_name != project_name:
        error_msg = f"Autosave error: Attempted to save content for project '{expected_project_name}' into project '{project_name}' directory at {filepath}"
        print(error_msg)
        return None  # Prevent saving to the wrong project

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print("Autosaved scene to", filepath)
    except Exception as e:
        print("Error during autosave:", e)
        return None

    cleanup_old_autosaves(project_folder, scene_identifier)
    return filepath
