import time
from sentence_transformers import SentenceTransformer
import warnings

warnings.filterwarnings("ignore")

print("Loading Jina Nano...")
model = SentenceTransformer(
    "jinaai/jina-embeddings-v5-text-nano", trust_remote_code=True
)

start = time.time()
model.encode(["OSPF area 0 configuration"], task="retrieval")
end = time.time()
print(f"Jina Nano Query Latency: {end - start:.4f}s")

print("Loading BGE Small...")
model_bge = SentenceTransformer("BAAI/bge-small-en-v1.5")

start = time.time()
model_bge.encode(["OSPF area 0 configuration"])
end = time.time()
print(f"BGE Small Query Latency: {end - start:.4f}s")
