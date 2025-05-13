# prompt_handler.py
import json
import os

from langchain.prompts import PromptTemplate
from settings.llm_api_aggregator import WWApiAggregator


def assemble_final_prompt(prompt_config, user_input, additional_vars=None, current_scene_text=None, extra_context=None):
    """
    Assemble a final prompt using a configurable PromptTemplate.
    
    Args:
        prompt_config (dict): Configuration from prompts.json with 'text' and optional 'variables'.
        user_input (str): The user's input (e.g., action beats).
        additional_vars (dict, optional): Extra variables to inject (e.g., {'pov': 'First Person'}).
        current_scene_text (str, optional): Current scene content.
        extra_context (str, optional): Additional context from the context panel.
    
    Returns:
        PromptTemplate: The assembled prompt ready for invocation.
    """
    # Extract prompt text and variables from config
    prompt_text = prompt_config.get("text", "Write a story chapter based on the following user input")
    expected_vars = prompt_config.get("variables", [])  # e.g., ["pov", "tense"]

    # Base template structure
    base_template = """
    ### System
    {system_prompt}

    ### Context
    {context}

    ### Story Up-to-now
    {story_so_far}

    ### User
    {user_input}
    """

    # Dynamically append sections for additional variables
    if additional_vars:
        for var_name, var_value in additional_vars.items():
            base_template += f"\n### {var_name.capitalize()}\n{{{var_name}}}"
    
#    full_prompt_text = prompt_text + "\n" + base_template

    # Define default variables
    default_vars = {
        "system_prompt": prompt_text,
        "context": extra_context or "No additional context provided.",
        "story_so_far": current_scene_text or "No previous story content.",
        "user_input": user_input
    }

    # Merge additional variables (e.g., from UI settings or ad-hoc tags)
    if additional_vars:
        default_vars.update(additional_vars)

    # Create the PromptTemplate with all possible variables
    prompt_template = PromptTemplate(
        input_variables=list(set(expected_vars + list(default_vars.keys()))),
        template=base_template # was full_prompt_text
    )

    # Validate that all required variables are provided
    missing_vars = [var for var in prompt_template.input_variables if var not in default_vars]
    if missing_vars:
        raise ValueError(_("Missing variables for prompt: {}").format(missing_vars))

    # Invoke the template with the variables
    final_prompt = prompt_template.invoke(default_vars)
    return final_prompt

def preview_final_prompt(prompt_config, user_input, additional_vars=None, current_scene_text=None, extra_context=None):
    """Generate a preview of the final prompt as a string."""
    final_prompt = assemble_final_prompt(prompt_config, user_input, additional_vars, current_scene_text, extra_context)
    return final_prompt.text  # Return as plain text for display

def send_final_prompt(final_prompt, prompt_config=None, overrides=None):
    """
    Sends the final prompt to the LLM using settings from the prompt's configuration.
    The configuration should include keys such as "provider", "model", "timeout", and "api_key".

    If no prompt_config is provided, then any overrides passed will be used as the configuration.
    If the resulting configuration is missing an API key (and the provider isn't "Local"), 
    the function will attempt to load the API key from settings.json based on the provider.

    Additional overrides (if provided) are merged afterward.
    Returns the generated text.
    """
    # If prompt_config is not provided, treat 'overrides' as the prompt configuration.
    if prompt_config is None:
        prompt_config = overrides.copy() if overrides else {}
        overrides = {}

    # Build the dictionary of overrides from the prompt configuration.
    prompt_overrides = {
        "provider": prompt_config.get("provider", "Local"),
        "model": prompt_config.get("model", "Local Model"),
    }
    # Merge any additional overrides if provided.
    if overrides:
        prompt_overrides.update(overrides)

    try:
        # Send the prompt to the LLM API aggregator.
        return WWApiAggregator.send_prompt_to_llm(final_prompt, overrides=prompt_overrides)
    except Exception as e:
        return(f"Error sending prompt to LLM: {e}")