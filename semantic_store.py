import json
import pickle
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors

PROJECT_ROOT = Path(__file__).resolve().parent
KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "knowledge_archive"
INDEX_PATH = PROJECT_ROOT / "data" / "semantic_index.pkl"

class SemanticKnowledgeStore:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.samples = []
        self.embeddings = None
        self.nn = None

    def build_index(self):
        print(f"Building Semantic Index from {KNOWLEDGE_DIR}...")
        all_samples = []
        
        # Load all archived samples
        for file in KNOWLEDGE_DIR.glob("*.jsonl"):
            with file.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        # We index the 'input' or 'instruction' + 'input'
                        text_to_index = f"{data.get('instruction', '')} {data.get('input', '')}"
                        if text_to_index.strip():
                            all_samples.append({
                                "text": text_to_index,
                                "output": data.get("output", ""),
                                "metadata": data.get("metadata", {})
                            })
                    except:
                        continue
        
        self.samples = all_samples
        texts = [s["text"] for s in all_samples]
        
        print(f"Encoding {len(texts)} samples (this might take a minute on M4)...")
        self.embeddings = self.model.encode(texts, show_progress_bar=True)
        
        self.nn = NearestNeighbors(n_neighbors=5, metric="cosine")
        self.nn.fit(self.embeddings)
        
        # Save for persistence
        with open(INDEX_PATH, "wb") as f:
            pickle.dump({"samples": self.samples, "embeddings": self.embeddings}, f)
        print(f"Index built and saved to {INDEX_PATH}")

    def load_index(self):
        if not INDEX_PATH.exists():
            self.build_index()
            return
            
        with open(INDEX_PATH, "rb") as f:
            data = pickle.load(f)
            self.samples = data["samples"]
            self.embeddings = data["embeddings"]
            
        self.nn = NearestNeighbors(n_neighbors=5, metric="cosine")
        self.nn.fit(self.embeddings)
        print(f"Loaded {len(self.samples)} samples into Semantic Store.")

    def search(self, query: str, k=3):
        if self.nn is None:
            self.load_index()
            
        query_emb = self.model.encode([query])
        distances, indices = self.nn.kneighbors(query_emb, n_neighbors=k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            results.append({
                "sample": self.samples[idx],
                "score": 1 - distances[0][i]
            })
        return results

if __name__ == "__main__":
    store = SemanticKnowledgeStore()
    store.build_index()
    
    # Test query
    test_q = "Red 40 in gummy bears safety audit"
    hits = store.search(test_q)
    print(f"\nTest Query: {test_q}")
    for h in hits:
        print(f"- [Score {h['score']:.2f}] {h['sample']['output'][:100]}...")
