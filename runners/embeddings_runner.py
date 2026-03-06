# -*- coding: utf-8 -*-

# embeddings
from embeddings import OpenAIEmbeddingModel, GeminiEmbeddingModel

# import embedding analysis
from analysis import EmbeddingAnalysis

# handle embeddings
def handle_embeddings(args: dict) -> None:
    '''
    Handle the embeddings command.

    :param args: The arguments to be passed to the embeddings command.
    :type args: dict

    :return: None
    :rtype: None
    '''
    embedding_model_map = {
        'gemini-embedding-001': 'Gemini',
        'text-embedding-ada-002': 'OpenAI',
        'text-embedding-3-small': 'OpenAI',
        'text-embedding-3-large': 'OpenAI'
    }

    # dispatch map for embedding models
    embedding_model_classes = {
        'Gemini': GeminiEmbeddingModel,
        'OpenAI': OpenAIEmbeddingModel,
    }

    # get model name
    model = args['model']
    provider = embedding_model_map.get(model)
    if not provider:
        raise ValueError(f'Unsupported embedding model: {model}')

    # select and instantiate embedding model
    model_class = embedding_model_classes[provider]
    vector_model = model_class(model_name=model)

    # embedding analysis
    embedding_analysis = EmbeddingAnalysis(
        vector_model=vector_model, args=args
    )

    # run embedding analysis
    print(f'Computing embeddings using {provider} {model}...')
    embedding_analysis.run_embedding_analysis()
