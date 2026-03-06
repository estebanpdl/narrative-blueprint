# -*- coding: utf-8 -*-

'''
Embedding analysis: Analyze narratives using vector embeddings.
It uses embeddings to measure semantic similarity and detect communities.
'''

# import modules
import os
import csv
import json
import pandas as pd
import networkx as nx

# sklearn and community detection
from sklearn.metrics.pairwise import cosine_similarity
from networkx.algorithms.community import louvain_communities

# embeddings
from embeddings import VectorModel

# MongoDB connection
from databases import MongoDBManager

# Embedding Analysis class
class EmbeddingAnalysis:
    '''
    EmbeddingAnalysis class
    '''
    def __init__(self, vector_model: VectorModel, args: dict = None):
        '''
        Initializes the EmbeddingAnalysis pipeline, validating input arguments
        and preparing the dataset for embedding analysis.

        :param vector_model: The vector model to be used for embedding analysis.
        :type vector_model: VectorModel

        :raises TypeError: If the provided `vector_model` is not a subclass
            of `VectorModel`.

        :param args: Additional arguments to be passed to the EmbeddingAnalysis class.
        :type args: dict
        '''
        # get arguments
        args = args or {}
        self.args = args

        # vector model
        if not isinstance(vector_model, VectorModel):
            raise TypeError('vector_model must be an instance of VectorModel')

        self.vector_model = vector_model

        # load narratives
        narrative_path = self.args.get('narrative_path')
        if not narrative_path:
            raise ValueError('The `narrative_path` argument is required')

        self.narratives = self._load_narratives(narrative_path)

        # check required columns in narratives dataset
        required_columns = ['narrative', 'uuid']
        missing_columns = [
            col for col in required_columns
            if col not in self.narratives.columns
        ]
        if missing_columns:
            raise ValueError(
                f'Narratives dataset missing required columns: {missing_columns}'
            )

        # output path
        self.output_path = self.args['output']
        if not os.path.exists(self.output_path):
            os.makedirs(self.output_path)

        # MongoDB connection
        self.mongo_db_name = self.args['mongo_db_name']
        self.mongo_collection_name = self.args['mongo_collection_name']
        self.mongodb_manager = MongoDBManager(
            db_name=self.mongo_db_name,
            collection_name=self.mongo_collection_name
        )

        # community analysis results
        self.threshold = self.args['threshold']
        self.analysis_results = {
            'total_communities': 0,
            'communities': []
        }

    def _load_narratives(self, path: str) -> pd.DataFrame:
        '''
        Load the narratives from a CSV, XLSX, or JSON file.

        :param path: The path to the file containing the narratives.
            Supported formats: CSV, XLSX, JSON
        :type path: str

        :return: A pandas DataFrame containing the narratives.
        :rtype: pd.DataFrame
        '''
        try:
            file_extension = os.path.splitext(path)[1].lower()

            if file_extension == '.csv':
                return pd.read_csv(path, encoding='utf-8', low_memory=False)

            elif file_extension in ['.xlsx', '.xls']:
                return pd.read_excel(path)

            elif file_extension == '.json':
                with open(path, 'r', encoding='utf-8') as file:
                    data = json.load(file)

                if isinstance(data, list):
                    return pd.DataFrame(data)
                elif isinstance(data, dict):
                    return pd.DataFrame([data])
                else:
                    raise ValueError(f'Unsupported JSON structure in {path}')

            else:
                raise ValueError(
                    f'Unsupported file format: {file_extension}. '
                    'Supported formats: .csv, .xlsx, .xls, .json'
                )

        except Exception as e:
            raise ValueError(f'Error loading narratives from {path}: {str(e)}')

    def _embedding_projector(self, narratives: list[str],
                             embeddings: list[list[float]]) -> None:
        '''
        Project embeddings into TensorFlow's embedding projector.

        :param narratives: The narratives to be projected.
        :type narratives: list[str]

        :param embeddings: The embeddings to be projected.
        :type embeddings: list[list[float]]
        '''
        if len(narratives) != len(embeddings):
            raise ValueError('The number of narratives and embeddings must be the same')

        # write embeddings metadata file
        with open(f'{self.output_path}/_tensor.tsv', 'w', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter='\t')
            for embedding in embeddings:
                writer.writerow(embedding)

        # write narratives metadata file
        with open(f'{self.output_path}/_metadata.tsv', 'w', encoding='utf-8') as f:
            for narrative in narratives:
                f.write(narrative + '\n')

    def _build_similarity_graph(self,
                                narratives: list[str],
                                embeddings: list[list[float]],
                                threshold: float = 0.75) -> nx.Graph:
        '''
        Builds a similarity graph from the given narratives and embeddings.

        :param narratives: The narratives to be used for building the graph.
        :type narratives: list[str]

        :param embeddings: The embeddings to be used for building the graph.
        :type embeddings: list[list[float]]

        :param threshold: The threshold to be used for building the graph.
        :type threshold: float

        :return: A similarity graph.
        :rtype: nx.Graph
        '''
        # compute similarity matrix
        similarity_matrix = cosine_similarity(embeddings)

        # graph
        G = nx.Graph()
        for i in range(len(narratives)):
            for j in range(i + 1, len(narratives)):
                if similarity_matrix[i][j] >= threshold:
                    G.add_edge(
                        i,
                        j,
                        weight=similarity_matrix[i][j],
                        similarity=similarity_matrix[i][j],
                        narrative_pair=(narratives[i], narratives[j]),
                        embedding_pair=(embeddings[i], embeddings[j])
                    )

        # add nodes
        for node in G.nodes:
            G.nodes[node]['narrative'] = narratives[node]

        return G

    def _analyze_communities(self, G: nx.Graph,
                             narratives: list[str]) -> None:
        '''
        Analyzes the communities in the similarity graph.

        :param G: NetworkX graph
        :type G: nx.Graph

        :param narratives: The narratives to be used for the analysis.
        :type narratives: list[str]
        '''
        communities = louvain_communities(G, seed=42)
        for idx, community in enumerate(communities):
            if len(community) >= 2:
                community_narratives = list(set([narratives[node] for node in community]))

                # get all edges
                community_edges = []
                unique_pairs = set()
                for edge in G.edges(data=True):
                    node1, node2, attrs = edge
                    if node1 in community or node2 in community:
                        pair_key = tuple(sorted((node1, node2)))
                        if pair_key not in unique_pairs:
                            unique_pairs.add(pair_key)
                            community_edges.append(
                                {
                                    'nodes': (node1, node2),
                                    'similarity': attrs['similarity'],
                                    'narratives': attrs['narrative_pair'],
                                    'embedding': attrs['embedding_pair']
                                }
                            )

                # avg similarity
                avg_similarity = sum(edge['similarity'] for edge in community_edges) \
                    / len(community_edges) if community_edges else 0

                # build community info
                community_info = {
                    'size': len(community),
                    'nodes': list(community),
                    'narratives': community_narratives,
                    'edges': community_edges,
                    'avg_similarity': avg_similarity
                }

                # add community info to analysis results
                self.analysis_results['total_communities'] += 1
                self.analysis_results['communities'].append(community_info)

        return

    def _export_community_analysis(self) -> None:
        '''
        Exports community analysis results to Excel files.
        '''
        # export detailed community narratives
        detailed_data = []
        for idx, community in enumerate(self.analysis_results['communities']):
            for narrative in community['narratives']:
                detailed_data.append({
                    'narrative': narrative
                })

        # export to XLSX
        detailed_df = pd.DataFrame(detailed_data)
        detailed_df.to_excel(
            f'{self.output_path}/community_narratives.xlsx',
            index=False
        )

        # export similarity pairs
        pairs_data = []
        for community in self.analysis_results['communities']:
            for edge in community['edges']:
                pairs_data.append({
                    'node1': edge['nodes'][0],
                    'node2': edge['nodes'][1],
                    'similarity': edge['similarity'],
                    'narrative1': edge['narratives'][0],
                    'narrative2': edge['narratives'][1]
                })

        # export to XLSX
        pairs_df = pd.DataFrame(pairs_data)
        pairs_df.to_excel(
            f'{self.output_path}/community_similarity_pairs.xlsx',
            index=False
        )

        return

    def run_similarity_analysis(self,
                                narratives: list[str],
                                embeddings: list[list[float]],
                                threshold: float = 0.75) -> None:
        '''
        Runs the similarity analysis.

        :param narratives: The narratives to be used for the similarity analysis.
        :type narratives: list[str]

        :param embeddings: The embeddings to be used for the similarity analysis.
        :type embeddings: list[list[float]]

        :param threshold: The threshold to be used for the similarity matrix.
        :type threshold: float
        '''
        # split narratives data into batches
        batch_size = 1000
        batch_narratives = [
            narratives[i:i+batch_size]
            for i in range(0, len(narratives), batch_size)
        ]

        batch_embeddings = [
            embeddings[i:i+batch_size]
            for i in range(0, len(embeddings), batch_size)
        ]

        # build similarity graph for each batch
        for narratives, embeddings in zip(batch_narratives, batch_embeddings):
            G = self._build_similarity_graph(
                narratives=narratives,
                embeddings=embeddings,
                threshold=threshold
            )

            # analyze communities
            self._analyze_communities(G, narratives)

        # extract results from analysis
        narratives_above_threshold = [
            n
            for community in self.analysis_results['communities']
            for edge in community['edges']
            for n in edge['narratives']
        ]

        embeddings_above_threshold = [
            e
            for community in self.analysis_results['communities']
            for edge in community['edges']
            for e in edge['embedding']
        ]

        # unique narratives and embeddings
        unique_narratives = []
        unique_embeddings = []
        for idx, narrative in enumerate(narratives_above_threshold):
            if narrative not in unique_narratives:
                unique_narratives.append(narrative)
                unique_embeddings.append(embeddings_above_threshold[idx])
        unique_narratives = list(unique_narratives)

        if len(unique_narratives) == 0 or len(unique_embeddings) == 0:
            print('WARNING: No narratives found above threshold. Skipping final similarity analysis.')
            return

        # rebuild similarity graph
        G = self._build_similarity_graph(
            narratives=unique_narratives,
            embeddings=unique_embeddings,
            threshold=threshold
        )

        # analyze communities
        self.analysis_results = {
            'total_communities': 0,
            'communities': []
        }
        self._analyze_communities(G, unique_narratives)

        # export community analysis
        self._export_community_analysis()

    def run_embedding_analysis(self) -> None:
        '''
        Runs the full pipeline to embed narratives.
        '''
        narratives = self.narratives['narrative'].tolist()
        uuids = self.narratives['uuid'].tolist()

        # compute embeddings
        self.vector_model.compute_embeddings(
            uuids=uuids,
            data=narratives,
            mongo_db_name=self.mongo_db_name,
            mongo_collection_name=self.mongo_collection_name
        )

        # load embeddings from MongoDB
        documents = self.mongodb_manager.get_documents()

        # writing embeddings to projector
        print ('')
        print ('Writing embeddings for Embedding Projector...')
        print ('Visit: https://projector.tensorflow.org/')
        self._embedding_projector(
            narratives=[item['text'] for item in documents],
            embeddings=[item['embedding'] for item in documents]
        )
        print ('Done.')

        # run similarity analysis
        print ('')
        print ('Running similarity analysis...')
        self.run_similarity_analysis(
            narratives=[item['text'] for item in documents],
            embeddings=[item['embedding'] for item in documents],
            threshold=self.threshold
        )
        print ('Finished.')

        return
