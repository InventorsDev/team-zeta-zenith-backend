# app/analytics/similarity_detector.py
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class SimilarityDetector:
    def __init__(self, model_name="all-MiniLM-L6-v2", cluster_count=5, duplicate_threshold=0.9):
        self.model = SentenceTransformer(model_name)
        self.cluster_count = cluster_count
        self.duplicate_threshold = duplicate_threshold
        self.embeddings = None
        self.ticket_texts = []

    def fit(self, ticket_texts):
        """Generate embeddings and perform clustering."""
        self.ticket_texts = ticket_texts
        self.embeddings = self.model.encode(ticket_texts, show_progress_bar=True)
        self.clusters = KMeans(n_clusters=self.cluster_count, random_state=42).fit_predict(self.embeddings)

    def find_similar(self, ticket_index, top_n=5):
        """Find top N similar tickets."""
        sim_matrix = cosine_similarity(self.embeddings)
        scores = sim_matrix[ticket_index]
        similar_indices = np.argsort(scores)[::-1][1:top_n+1]
        return [(self.ticket_texts[i], float(scores[i])) for i in similar_indices]

    def detect_duplicates(self):
        """Detect duplicates based on threshold."""
        sim_matrix = cosine_similarity(self.embeddings)
        duplicates = []
        for i in range(len(sim_matrix)):
            for j in range(i+1, len(sim_matrix)):
                if sim_matrix[i][j] >= self.duplicate_threshold:
                    duplicates.append((self.ticket_texts[i], self.ticket_texts[j], float(sim_matrix[i][j])))
        return duplicates
