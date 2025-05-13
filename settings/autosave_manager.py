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
    project_folder = os.path.join("Projects", sanitized_project)
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

def load_latest_autosave(project_name: str, hierarchy: list, node: dict = None) -> str | None:
    """
    Load the content of the most recent autosave file for a given scene.

    Parameters:
        project_name (str): The name of the project.
        hierarchy (list): List of [act, chapter, scene] names for fallback file lookup.
        node (dict, optional): The node containing 'latest_file' if available.

    Returns the content if found, or None otherwise.
    """
    uuid_val = node.get("uuid") if node else None

    # Helper function to extract UUID from file content
    def get_uuid_from_file(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line.startswith("<!-- UUID:"):
                    return first_line.split("<!-- UUID:")[1].split("-->")[0].strip()
                return None
        except Exception:
            return None

    # Try loading from node's latest_file if provided
    if node and "latest_file" in node and os.path.exists(node["latest_file"]):
        filepath = node["latest_file"]
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                if content.startswith("<!-- UUID:"):
                    content = "\n".join(content.split("\n")[1:])
                return content
        except Exception as e:
            print(f"Error loading latest file {node['latest_file']}: {e}")

    # Fallback to hierarchy-based lookup
    latest_file = get_latest_autosave_path(project_name, hierarchy)
    if latest_file:
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                content = f.read()
                if content.startswith("<!-- UUID:"):
                    content = "\n".join(content.split("\n")[1:])
                return content
        except Exception as e:
            print(f"Error loading autosave file {latest_file}: {e}")

    # If UUID is available but no match found, scan project folder as a last resort
    if uuid_val:
        project_folder = get_project_folder(project_name)
        pattern = os.path.join(project_folder, f"*{NEW_FILE_EXTENSION}")
        autosave_files = glob.glob(pattern)
        for filepath in sorted(autosave_files, key=os.path.getmtime, reverse=True):
            file_uuid = get_uuid_from_file(filepath)
            if file_uuid == uuid_val:
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        if content.startswith("<!-- UUID:"):
                            content = "\n".join(content.split("\n")[1:])
                        return content
                except Exception as e:
                    print(f"Error loading autosave file {filepath}: {e}")
                # Update node's latest_file if found
                if node and "latest_file" in node:
                    node["latest_file"] = filepath
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

def save_scene(project_name: str, hierarchy: list, uuid: str, content: str, expected_project_name: str = None) -> str:
    """
    Save the scene content if it has changed since the last autosave.
    Uses the UUID and name for identification and file naming.

    Parameters:
        project_name (str): The name of the project.
        hierarchy (list): List of [act, chapter, scene] names for file naming.
        uuid (str): The UUID of the node being saved.       
        content (str): The scene content to save (HTML formatted).
        expected_project_name (str, optional): The project name expected by the caller for validation.
    
    Returns:
        The filepath of the new autosave file if saved, or None if no changes were detected.
    """

    scene_identifier = build_scene_identifier(project_name, hierarchy)

    # Check if the scene content has changed.
    last_content = load_latest_autosave(project_name, hierarchy)
    if last_content is not None and last_content.strip() == content.strip():
        print("No changes detected since the last autosave. Skipping autosave.")
        return None

    project_folder = get_project_folder(project_name)
    timestamp = time.strftime("%Y%m%d%H%M%S")
    filename = f"{scene_identifier}_{timestamp}{NEW_FILE_EXTENSION}"
    filepath = os.path.join(project_folder, filename)

    # Validate project directory if expected_project_name is provided
    if expected_project_name and expected_project_name != project_name:
        error_msg = f"Autosave error: Attempted to save content for project '{expected_project_name}' into project '{project_name}' directory at {filepath}"
        print(error_msg)
        return None  # Prevent saving to the wrong project

    # Embed UUID in the HTML content
    content_with_uuid = f"<!-- UUID: {uuid} -->\n{content}"

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content_with_uuid)
        print("Autosaved scene to", filepath)
    except Exception as e:
        print("Error during autosave:", e)
        return None

    cleanup_old_autosaves(project_folder, scene_identifier)
    return filepath

