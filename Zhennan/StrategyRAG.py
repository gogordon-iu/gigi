"""
Offline RAG strategy retriever.
Uses sentence-transformers (all-MiniLM-L6-v2, ~22MB) to embed student input
and retrieve the most relevant strategy from the catalog — no LLM call needed.

Embeddings are pre-computed once at startup for zero per-turn overhead.
"""

import numpy as np
from sentence_transformers import SentenceTransformer
from strategy_catalog import StrategyCatalog, Strategy


class StrategyRAG:
    def __init__(self, catalog: StrategyCatalog, model_name: str = "all-MiniLM-L6-v2"):
        """
        Args:
            catalog: StrategyCatalog instance.
            model_name: Small offline sentence-transformer model.
                        'all-MiniLM-L6-v2' is 22MB and runs fine on CPU.
        """
        self.catalog = catalog
        self.strategies: list[Strategy] = catalog.get_all_strategies()

        print("[StrategyRAG] Loading embedding model...")
        self.model = SentenceTransformer(model_name)

        # Build embedding corpus: combine trigger + name for richer matching
        self.corpus = [
            f"{s.trigger} {s.name}"
            for s in self.strategies
        ]

        print("[StrategyRAG] Pre-computing strategy embeddings...")
        self.embeddings = self.model.encode(
            self.corpus,
            convert_to_numpy=True,
            normalize_embeddings=True,  # enables fast dot-product cosine similarity
            show_progress_bar=False
        )
        print(f"[StrategyRAG] Ready — {len(self.strategies)} strategies indexed.")

    def retrieve(self, student_input: str, top_k: int = 1) -> list[Strategy]:
        """
        Given a student utterance, return the top_k most relevant strategies.

        Args:
            student_input: Raw text from the student.
            top_k: Number of strategies to return.

        Returns:
            List of Strategy objects, best match first.
        """
        if not student_input or not student_input.strip():
            # Fallback: return first strategy if input is empty
            return self.strategies[:top_k]

        query_vec = self.model.encode(
            [student_input],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        # Cosine similarity via dot product (vectors are already normalized)
        scores = self.embeddings @ query_vec.T  # shape: (n_strategies, 1)
        top_indices = np.argsort(scores[:, 0])[::-1][:top_k]

        return [self.strategies[i] for i in top_indices]

    def retrieve_hint(self, student_input: str) -> str:
        """
        Convenience method: returns a single short hint string for the LLM prompt.
        E.g. "Encourage curiosity. Ask an imaginative question."
        """
        best = self.retrieve(student_input, top_k=1)
        if not best:
            return ""
        s = best[0]
        return f"{s.robot_actions}"