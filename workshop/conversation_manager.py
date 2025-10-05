import json
import logging
import os

class ConversationManager:
    def __init__(self, file_path="conversations.json"):
        self.file_path = file_path
        self.conversations = {}
        self.last_viewed_chat = None
        self.load()

    def load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                version = data.get("version", 0)
                if version == 0:
                    if isinstance(data, dict) and all(isinstance(k, str) and isinstance(v, list) for k, v in data.items()):
                        # Old format
                        self.conversations = {k: {"mode": "Writing Coach", "messages": v, "pov_character": None} for k, v in data.items()}
                        self.last_viewed_chat = list(data.keys())[0] if data else "Chat 1"
                    else:
                        self.conversations = data.get("conversations", {"Chat 1": {"mode": "Writing Coach", "messages": [], "pov_character": None}})
                        self.last_viewed_chat = data.get("last_viewed_chat", "Chat 1")
                        for conv in self.conversations.values():
                            if "pov_character" not in conv:
                                conv["pov_character"] = None
                elif version == 1:
                    self.conversations = data.get("conversations", {"Chat 1": {"mode": "Writing Coach", "messages": [], "pov_character": None}})
                    self.last_viewed_chat = data.get("last_viewed_chat", "Chat 1")
                self._ensure_default_conversation()
            except Exception as e:
                logging.error(f"Error loading conversations: {e}", exc_info=True)
                self._initialize_default()
        else:
            self._initialize_default()

    def _ensure_default_conversation(self):
        if not self.conversations:
            self.conversations = {"Chat 1": {"mode": "Writing Coach", "messages": [], "pov_character": None}}
            self.last_viewed_chat = "Chat 1"

    def _initialize_default(self):
        self.conversations = {"Chat 1": {"mode": "Writing Coach", "messages": [], "pov_character": None}}
        self.last_viewed_chat = "Chat 1"

    def save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump({
                    "version": 1,
                    "conversations": self.conversations,
                    "last_viewed_chat": self.last_viewed_chat
                }, f, indent=4)
            logging.debug("Conversations saved successfully")
        except Exception as e:
            logging.error(f"Error saving conversations: {e}", exc_info=True)

    def add_conversation(self, name, mode, pov_character=None):
        if name in self.conversations:
            raise ValueError(f"Conversation '{name}' already exists")
        self.conversations[name] = {"mode": mode, "messages": [], "pov_character": pov_character}
        self.last_viewed_chat = name

    def rename_conversation(self, old_name, new_name):
        if old_name not in self.conversations:
            raise ValueError(f"Conversation '{old_name}' not found")
        if new_name in self.conversations:
            raise ValueError(f"Conversation '{new_name}' already exists")
        self.conversations[new_name] = self.conversations.pop(old_name)
        if self.last_viewed_chat == old_name:
            self.last_viewed_chat = new_name

    def delete_conversation(self, name):
        if name not in self.conversations:
            raise ValueError(f"Conversation '{name}' not found")
        del self.conversations[name]
        if self.last_viewed_chat == name:
            self.last_viewed_chat = list(self.conversations.keys())[0] if self.conversations else None

    def get_conversation_names(self):
        return list(self.conversations.keys())

    def get_conversation(self, name):
        return self.conversations.get(name, {"mode": "Writing Coach", "messages": [], "pov_character": None})

    def update_messages(self, name, messages):
        if name in self.conversations:
            self.conversations[name]["messages"] = messages

    def get_mode(self, name):
        return self.conversations.get(name, {}).get("mode", "Writing Coach")

    def get_pov_character(self, name):
        return self.conversations.get(name, {}).get("pov_character", None)

    def get_icon_path(self, mode):
        return "assets/icons/book.svg" if mode == "Writing Coach" else "assets/icons/user.svg"

    def set_last_viewed(self, name):
        if name in self.conversations:
            self.last_viewed_chat = name