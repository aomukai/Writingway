from .conversation_manager import ConversationManager
from .embedding_manager import EmbeddingIndex

class WorkshopModel:
    def __init__(self, parent_model=None):
        self.project_name = getattr(parent_model, "project_name", "DefaultProject") if parent_model else "DefaultProject"
        self.structure = getattr(parent_model, "structure", {"acts": []}) if parent_model else {"acts": []}
        self.conversation_manager = ConversationManager()
        self.embedding_index = EmbeddingIndex()
