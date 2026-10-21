# -*- coding: utf-8 -*-

# import modules
import json
from narrative_blueprint.resources import load_model_limits

# language models
from .model import LanguageModel
from .openai_client import OpenAIGPT
from .gemini_client import GeminiModels

# map providers to their model classes
_PROVIDER_CLASS_MAP = {
    'openai': OpenAIGPT,
    'google': GeminiModels
}

def get_llm_engine(model_name: str) -> LanguageModel:
    '''
    Factory function to get the appropriate LLM engine for a model.
    
    :param model_name: The name of the model (e.g., 'gpt-4o-mini', 'gemini-2.5-flash-preview-05-20')
    :return: An instance of the appropriate LLM class
    :raises ValueError: If the model is not found in model_limits.json
    '''
    # Load model limits config
    model_limits = load_model_limits()
    
    # get model
    for provider, models in model_limits.items():
        if model_name in models:
            print (f'Using {provider} for {model_name}')
            print ('')
            return _PROVIDER_CLASS_MAP[provider](model_name)
    
    raise ValueError(f"Model {model_name} not found in model_limits.json")
