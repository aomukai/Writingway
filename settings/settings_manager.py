import json
import os, re
import copy
import logging
from typing import Any, Dict, Optional, List, Union
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.WARN,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

class SettingsManager:
    """
    Manages application settings by handling loading, saving, and value changes
    of a settings.json file. Ensures that file contents always match memory values.
    """
    DEFAULT_SETTINGS = {
        "version": "1",
        "general": {
            "fast_tts": False,
            "enable_autosave": False,
            "language": "Language"
        },
        "appearance": {
            "theme": "Ocean Breeze",
            "background_color": "#FFFFFF",
            "text_size": 12
        },
        "llm_configs": {
            "OpenAI": {
                "provider": "OpenAI",
                "endpoint": "https://api.openai.com/v1",
                "model": "gpt-3.5-turbo",
                "api_key": "",
                "timeout": 30
            },
            "Ollama": {
                "provider": "Ollama",
                "endpoint": "http://localhost:11434/v1",
                "api_key": "",
                "timeout": 240
            },
            "OpenRouter": {
                "provider": "OpenRouter",
                "endpoint": "https://openrouter.ai/api/v1/",
                "model": "",
                "api_key": "",
                "timeout": 60
            },
            "LMStudio": {
                "provider": "LMStudio",
                "endpoint": "",
                "model": "",
                "api_key": "",
                "timeout": 30
            }
        },
        "active_llm_config": "OpenAI"
    }

    def __init__(self, file_path: Union[str, Path] = "settings.json"):
        """
        Initialize the settings manager with the path to the settings file.
        
        Args:
            file_path: Path to the settings.json file
        """
        self.logger = logging.getLogger(__name__)
        self.file_path = Path(file_path)
        self.settings = copy.deepcopy(self.DEFAULT_SETTINGS)
        self._load_settings()

    def _load_settings(self) -> None:
        """Load settings from the file, creating a new one if it doesn't exist."""
        try:
            if self.file_path.exists():
                with open(self.file_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                
                # Check version and handle backward compatibility
                if "version" not in data:
                    data = self._convert_old_settings(data)
                
                # Update settings with loaded data
                self.settings.update(data)
                self.logger.info(f"Settings loaded successfully from {self.file_path}")
            else:
                # Create a new settings file with defaults
                self._save_settings()
                self.logger.info(f"Created new settings file at {self.file_path}")
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"Error loading settings: {str(e)}")
            # If there's an error, create a backup of the corrupt file if it exists
            if self.file_path.exists():
                backup_path = self.file_path.with_suffix('.json.bak')
                try:
                    # Copy the corrupt file to a backup
                    with open(self.file_path, 'r', encoding='utf-8') as src:
                        with open(backup_path, 'w', encoding='utf-8') as dst:
                            dst.write(src.read())
                    self.logger.info(f"Corrupt settings file backed up to {backup_path}")
                except IOError as backup_error:
                    self.logger.error(f"Failed to create backup: {str(backup_error)}")
            
            # Reset to defaults and save
            self.settings = copy.deepcopy(self.DEFAULT_SETTINGS)
            self._save_settings()
            self.logger.info("Reset to default settings due to error")

    def _save_settings(self) -> bool:
        """
        Save current settings to the file.
        
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            # Ensure the directory exists
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write settings to file with pretty formatting
            with open(self.file_path, 'w', encoding='utf-8') as file:
                json.dump(self.settings, file, indent=4, ensure_ascii=False)
            
            self.logger.info(f"Settings saved successfully to {self.file_path}")
            return True
        except IOError as e:
            self.logger.error(f"Error saving settings: {str(e)}")
            return False

    def _convert_old_settings(self, old_settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert old settings format to the current version.
        
        Args:
            old_settings: The settings in the old format
            
        Returns:
            Dict containing the converted settings in the current format
        """
        self.logger.info("Converting old settings format to current version")
        
        # Start with default settings and update with conversions
        new_settings = copy.deepcopy(self.DEFAULT_SETTINGS)
        
        try:
            # Convert appearance settings
            if "theme" in old_settings:
                new_settings["appearance"]["theme"] = old_settings["theme"]
            
            # Convert general settings
            if "tts_fast" in old_settings:
                new_settings["general"]["fast_tts"] = old_settings["tts_fast"]
            
            if "autosave" in old_settings:
                new_settings["general"]["enable_autosave"] = old_settings["autosave"]
            
            # Convert LLM configs
            if "llm_configs" in old_settings and isinstance(old_settings["llm_configs"], list):
                new_llm_configs = {}
                
                for config in old_settings["llm_configs"]:
                    if "name" in config and isinstance(config, dict):
                        name = config.pop("name")
                        new_llm_configs[name] = config
                        
                        # Ensure required fields exist in each config
                        for key in ["provider", "endpoint", "api_key", "timeout"]:
                            if key not in config:
                                config[key] = ""
                        
                        # Add model field if it doesn't exist
                        if "model" not in config:
                            config["model"] = ""
                                     
                        # Truncate endpoint after "/v1/"
                        if "endpoint" in config:
                            endpoint = config["endpoint"]
                            if "/v1/" in endpoint:
                                config["endpoint"] = endpoint.split("/v1/")[0] + "/v1/"
           
                # Update LLM configs if we found any valid ones
                if new_llm_configs:
                    new_settings["llm_configs"] = new_llm_configs
                    
                    # Set active LLM config to the first one if available
                    if list(new_llm_configs.keys()):
                        new_settings["active_llm_config"] = list(new_llm_configs.keys())[0]
            
            self.logger.info("Old settings successfully converted")
            return new_settings
            
        except Exception as e:
            self.logger.error(f"Error converting old settings: {str(e)}")
            return new_settings  # Return defaults if conversion fails

    def get_general_settings(self) -> Dict[str, Any]:
        """
        Get all general settings.
        
        Returns:
            Dictionary containing general settings
        """
        return copy.deepcopy(self.settings.get("general", {}))

    def get_appearance_settings(self) -> Dict[str, Any]:
        """
        Get all appearance settings.
        
        Returns:
            Dictionary containing appearance settings
        """
        return copy.deepcopy(self.settings.get("appearance", {}))

    def get_llm_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all LLM configurations.
        
        Returns:
            Dictionary containing all LLM configurations
        """
        return copy.deepcopy(self.settings.get("llm_configs", {}))

    def get_active_llm_name(self) -> str:
        """
        Get the name of the active LLM configuration.
        
        Returns:
            The name of the active LLM configuration
        """
        return self.settings.get("active_llm_config", "")

    def get_active_llm_config(self) -> Optional[Dict[str, Any]]:
        """
        Get the active LLM configuration.
        
        Returns:
            Dictionary containing the active LLM configuration or None if not found
        """
        active_name = self.settings.get("active_llm_config")
        if active_name and active_name in self.settings.get("llm_configs", {}):
            return copy.deepcopy(self.settings["llm_configs"][active_name])
        return None

    def get_llm_config(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific LLM configuration by name.
        
        Args:
            name: The name of the LLM configuration to retrieve
            
        Returns:
            Dictionary containing the requested LLM configuration or None if not found
        """
        if name in self.settings.get("llm_configs", {}):
            return copy.deepcopy(self.settings["llm_configs"][name])
        return None

    def get_setting(self, category: str, key: str, default: Any = None) -> Any:
        """
        Get a specific setting by category and key.
        
        Args:
            category: The category of the setting (e.g., "general", "appearance")
            key: The key of the setting to retrieve
            default: Default value to return if the setting is not found
            
        Returns:
            The value of the setting or default if not found
        """
        if category in self.settings and key in self.settings[category]:
            return self.settings[category][key]
        return default

    def set_setting(self, category: str, key: str, value: Any) -> bool:
        """
        Set a specific setting by category and key, and immediately save to file.
        
        Args:
            category: The category of the setting (e.g., "general", "appearance")
            key: The key of the setting to set
            value: The value to set
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure category exists
            if category not in self.settings:
                self.settings[category] = {}
            
            # Update the setting
            self.settings[category][key] = value
            
            # Save to ensure file consistency
            return self._save_settings()
        except Exception as e:
            self.logger.error(f"Error setting {category}.{key}: {str(e)}")
            return False

    def update_llm_configs(self, configs: Dict[str, Dict[str, Any]], default: str) -> bool:
        """
        Update multiple LLM configurations at once with a dictionary.
        
        Args:
            configs: Dictionary containing LLM configurations to update
        """
        try:
            # Ensure llm_configs exists
            if "llm_configs" not in self.settings:
                self.settings["llm_configs"] = {}
            
            # Update or create the LLM configs
            for name, config in configs.items():
                self.settings["llm_configs"][name] = copy.deepcopy(config)
            self.settings["active_llm_config"] = default
            
            # Save to ensure file consistency
            return self._save_settings()
        except Exception as e:
            self.logger.error(f"Error updating multiple LLM configs: {str(e)}")
            return False

    def update_llm_config(self, name: str, config: Dict[str, Any]) -> bool:
        """
        Update an LLM configuration, creating it if it doesn't exist.
        
        Args:
            name: The name of the LLM configuration
            config: The configuration dictionary
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure llm_configs exists
            if "llm_configs" not in self.settings:
                self.settings["llm_configs"] = {}
            
            # Update or create the LLM config
            self.settings["llm_configs"][name] = copy.deepcopy(config)
            
            # Save to ensure file consistency
            return self._save_settings()
        except Exception as e:
            self.logger.error(f"Error updating LLM config {name}: {str(e)}")
            return False

    def delete_llm_config(self, name: str) -> bool:
        """
        Delete an LLM configuration.
        
        Args:
            name: The name of the LLM configuration to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if the config exists
            if "llm_configs" in self.settings and name in self.settings["llm_configs"]:
                # If deleting the active config, change active to something else
                if self.settings.get("active_llm_config") == name:
                    remaining_configs = [k for k in self.settings["llm_configs"].keys() if k != name]
                    if remaining_configs:
                        self.settings["active_llm_config"] = remaining_configs[0]
                    else:
                        self.settings["active_llm_config"] = ""
                
                # Delete the config
                del self.settings["llm_configs"][name]
                
                # Save to ensure file consistency
                return self._save_settings()
            return False
        except Exception as e:
            self.logger.error(f"Error deleting LLM config {name}: {str(e)}")
            return False

    def set_active_llm_config(self, name: str) -> bool:
        """
        Set the active LLM configuration.
        
        Args:
            name: The name of the LLM configuration to set as active
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if the config exists
            if "llm_configs" in self.settings and name in self.settings["llm_configs"]:
                self.settings["active_llm_config"] = name
                
                # Save to ensure file consistency
                return self._save_settings()
            return False
        except Exception as e:
            self.logger.error(f"Error setting active LLM config to {name}: {str(e)}")
            return False

    def update_general_settings(self, settings_dict: Dict[str, Any]) -> bool:
        return self.update_settings("general", settings_dict)
    
    def update_appearance_settings(self, settings_dict: Dict[str, Any]) -> bool:
        return self.update_settings("appearance", settings_dict)

    def update_settings(self, category, settings_dict: Dict[str, Any]) -> bool:
        """
        Update multiple settings at once with a dictionary.
        
        Args:
            settings_dict: Dictionary containing settings to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Deep merge the settings
            self._deep_update(self.settings, category, settings_dict)
            
            # Save to ensure file consistency
            return self._save_settings()
        except Exception as e:
            self.logger.error(f"Error updating multiple settings: {str(e)}")
            return False

    def _deep_update(self, target: Dict[str, Any], category: str, source: Dict[str, Any]) -> None:
        """
        Recursively update a dictionary without overwriting entire nested dictionaries.
        
        Args:
            target: The dictionary to update
            source: The dictionary with updates
        """
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                # Recursively update nested dictionaries
                self._deep_update(target[key], value)
            else:
                # Set the value directly
                target[category][key] = copy.deepcopy(value)

    def reset_to_defaults(self) -> bool:
        """
        Reset all settings to default values.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.settings = copy.deepcopy(self.DEFAULT_SETTINGS)
            return self._save_settings()
        except Exception as e:
            self.logger.error(f"Error resetting to defaults: {str(e)}")
            return False

    def export_settings(self, export_path: Union[str, Path]) -> bool:
        """
        Export settings to a different file.
        
        Args:
            export_path: Path to export the settings to
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            export_path = Path(export_path)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(export_path, 'w', encoding='utf-8') as file:
                json.dump(self.settings, file, indent=4, ensure_ascii=False)
            
            self.logger.info(f"Settings exported successfully to {export_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error exporting settings: {str(e)}")
            return False

    def import_settings(self, import_path: Union[str, Path]) -> bool:
        """
        Import settings from a different file.
        
        Args:
            import_path: Path to import the settings from
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            import_path = Path(import_path)
            
            if not import_path.exists():
                self.logger.error(f"Import file does not exist: {import_path}")
                return False
            
            with open(import_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            # Check version and handle backward compatibility
            if "version" not in data:
                data = self._convert_old_settings(data)
            
            # Update settings with loaded data
            self.settings.update(data)
            
            # Save to ensure file consistency
            return self._save_settings()
        except Exception as e:
            self.logger.error(f"Error importing settings: {str(e)}")
            return False

    def sanitize(self, text):
        return re.sub(r'\W+', '', text)    
    
    def get_project_path(self, project_name = "", file = ""):
        """Return the path to the project directory and desanitze any filename therein."""
        return os.path.join(os.getcwd(), "Projects", self.sanitize(project_name), file)

WWSettingsManager = SettingsManager()

# Example usage
if __name__ == "__main__":
    settings = SettingsManager("settings.json")
    
    # Get values
    general = settings.get_general_settings()
    appearance = settings.get_appearance_settings()
    active_llm = settings.get_active_llm_config()
    
    # Change a setting
    settings.set_setting("general", "fast_tts", True)
    
    # Update LLM config
    settings.update_llm_config("Claude", {
        "provider": "Anthropic",
        "endpoint": "https://api.anthropic.com/v1",
        "model": "claude-3-opus-20240229",
        "api_key": "",
        "timeout": 120
    })
    
    # Set active LLM
    settings.set_active_llm_config("Claude")
    
    # Reset to defaults
    # settings.reset_to_defaults()
