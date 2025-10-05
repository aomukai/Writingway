## file: chat_session.py
import logging
import re
from .conversation_history_manager import estimate_conversation_tokens, summarize_conversation
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

TOKEN_LIMIT = 2000

class BaseChatSession:
    def __init__(self, mode, messages, context_panel, prompt_panel, embedding_index):
        self.mode = mode
        self.messages = messages
        self.context_panel = context_panel
        self.prompt_panel = prompt_panel
        self.embedding_index = embedding_index

    def validate(self):
        return True

    def get_system_prompt(self, prompt_config, compendium_text, story_text):
        return prompt_config.get("text", "")

    def augment_user_message(self, user_input, story_text, retrieved_context):
        augmented = user_input
        if story_text:
            augmented += f"\n\nStory Context:\n{story_text}"
        if retrieved_context:
            augmented += "\n\n[Retrieved Context]:\n" + "\n".join(retrieved_context)
        return augmented

    def construct_message(self, user_input):
        if not user_input:
            return None
        prompt_config = self.prompt_panel.get_prompt()
        overrides = self.prompt_panel.get_overrides() if prompt_config else {}
        compendium_text = self.context_panel.get_selected_compendium_text()
        story_text = self.context_panel.get_selected_story_text()
        system_prompt = self.get_system_prompt(prompt_config, compendium_text, story_text)
        retrieved_context = self.embedding_index.query(user_input)
        augmented_message = self.augment_user_message(user_input, story_text, retrieved_context)
        template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_prompt),
            HumanMessagePromptTemplate.from_template("{user_message}")
        ])
        lc_messages = template.format_messages(user_message=augmented_message)
        payload = list(self.messages)
        payload.append({"role": "system", "content": lc_messages[0].content})
        payload.append({"role": "user", "content": lc_messages[-1].content})
        if estimate_conversation_tokens(payload) > TOKEN_LIMIT:
            summary = summarize_conversation(payload, overrides=overrides)
            payload = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": summary}
            ]
        logging.debug(f"Constructed payload: {payload}")
        return payload

    def append_message(self, role, content):
        self.messages.append({"role": role, "content": content})

    def get_preview_payload(self):
        user_input = self.context_panel.parent().chat_input.toPlainText().strip()  # Assuming access via context_panel
        return self.construct_message(user_input)

class WritingCoachSession(BaseChatSession):
    def __init__(self, messages, context_panel, prompt_panel, embedding_index):
        super().__init__("Writing Coach", messages, context_panel, prompt_panel, embedding_index)

class RolePlaySession(BaseChatSession):
    def __init__(self, messages, context_panel, prompt_panel, embedding_index):
        super().__init__("Role Play", messages, context_panel, prompt_panel, embedding_index)

    def validate(self):
        compendium_text = self.context_panel.get_selected_compendium_text()
        if not compendium_text:
            return False
        return True

    def get_system_prompt(self, prompt_config, compendium_text, story_text):
        system_prompt = super().get_system_prompt(prompt_config, compendium_text, story_text)
        system_prompt += " Character details:\n{character_details}"
        return system_prompt.format(character_details=compendium_text)
