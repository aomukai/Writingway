import math
import tiktoken
from settings.llm_api_aggregator import WWApiAggregator
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

# Define the model name and get its encoding. Adjust the model name as needed.
MODEL_NAME = "gpt-3.5-turbo"
encoding = tiktoken.encoding_for_model(MODEL_NAME)

def estimate_tokens(text):
    """Estimate tokens using tiktoken for better accuracy."""
    return len(encoding.encode(text))

def estimate_conversation_tokens(conversation_history):
    total = 0
    for message in conversation_history:
        total += estimate_tokens(message.get("content", ""))
    return total

def should_preserve(text):
    """
    Check if a message contains protected text.
    For example, any text wrapped in asterisks (*) is marked as protected.
    You can enhance this function with a more complex tagging logic if needed.
    """
    return "*" in text

def summarize_conversation(conversation_history, max_tokens=500, overrides=None):
    """
    Summarize the conversation using ChatPromptTemplate and final_prompt to ensure the LLM treats the task as summarization.
    """
    # Build the conversation text while preserving protected messages
    filtered_messages = []
    for msg in conversation_history:
        content = msg.get("content", "")
        if should_preserve(content):
            filtered_messages.append(f'{msg["role"]}: {content}')
        else:
            filtered_messages.append(f'{msg["role"]}: {content}')
    conversation_text = "\n".join(filtered_messages)

    # Create ChatPromptTemplate for the conversation history
    template = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(
            "You are a summarization assistant. Your task is to summarize the conversation provided below. "
            "Do not respond to the conversation content or generate new dialogue. "
            "Provide only a summary of the conversation in up to {max_tokens} tokens."
        ),
        HumanMessagePromptTemplate.from_template("Conversation to summarize:\n{conversation_text}")
    ])

    # Format the prompt with the conversation text and max_tokens
    messages = template.format_messages(conversation_text=conversation_text, max_tokens=max_tokens)

    # Convert LangChain messages to the expected conversation payload format
    conversation_payload = [
        {"role": "system", "content": messages[0].content},
        {"role": "user", "content": messages[1].content}
    ]

    # Define the final_prompt to reinforce the summarization task
    final_prompt = (
        f"Summarize the following conversation in up to {max_tokens} tokens. "
        "Do not respond to the conversation content or generate new dialogue. "
        "Provide only a concise summary."
    )

    if not overrides:
        overrides = {}
    overrides.update({
        "max_tokens": max_tokens
    })

    # Send the prompt to the LLM
    summary = WWApiAggregator.send_prompt_to_llm(
        final_prompt=final_prompt,
        overrides=overrides,
        conversation_history=conversation_payload
    )
    return summary

def prune_conversation_history(conversation_history, token_limit):
    """
    Prune conversation history to fit within token_limit.
    This function tries to remove messages starting from index 1 (keeping the system prompt intact)
    and skips messages that are marked as protected (using our should_preserve() check).
    """
    index = 1  # Start after the system message
    # Continue while we exceed the token limit and have messages to remove
    while estimate_conversation_tokens(conversation_history) > token_limit and index < len(conversation_history):
        content = conversation_history[index].get("content", "")
        if not should_preserve(content):
            conversation_history.pop(index)
        else:
            index += 1  # Skip protected message
    return conversation_history