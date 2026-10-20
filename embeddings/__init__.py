# -*- coding: utf-8 -*-

from .base import VectorModel

__all__ = ['VectorModel', 'OpenAIEmbeddingModel', 'GeminiEmbeddingModel']


def __getattr__(name):
    if name == 'OpenAIEmbeddingModel':
        from .openai_embeddings import OpenAIEmbeddingModel
        return OpenAIEmbeddingModel
    if name == 'GeminiEmbeddingModel':
        from .gemini_embeddings import GeminiEmbeddingModel
        return GeminiEmbeddingModel
    raise AttributeError(name)
