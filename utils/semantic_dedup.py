# utils/semantic_dedup.py
import os
import time
import logging
import threading
from typing import Optional
import chromadb
from fastembed import TextEmbedding

logger = logging.getLogger("SemanticDeduplicator")

# Global singleton client and collection references
_chroma_client = None
_collection = None
_embedding_model = None

_init_lock = threading.Lock()

def get_embedding_model() -> Optional[TextEmbedding]:
    global _embedding_model
    if _embedding_model is None:
        with _init_lock:
            if _embedding_model is None:
                logger.info("[Semantic Dedup] Initializing local FastEmbed TextEmbedding model...")
                try:
                    _embedding_model = TextEmbedding()
                except Exception as e:
                    logger.warning(f"[Semantic Dedup] FastEmbed model init failed: {e}. Attempting cache cleanup...")
                    try:
                        import tempfile, shutil
                        cache_dir = os.path.join(tempfile.gettempdir(), "fastembed_cache")
                        if os.path.exists(cache_dir):
                            shutil.rmtree(cache_dir, ignore_errors=True)
                        _embedding_model = TextEmbedding()
                    except Exception as retry_err:
                        logger.error(f"[Semantic Dedup] FastEmbed fallback failed: {retry_err}")
                        _embedding_model = None
    return _embedding_model

def get_chroma_collection():
    global _chroma_client, _collection
    if _collection is None:
        with _init_lock:
            if _collection is None:
                try:
                    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    chroma_path = os.path.join(base_dir, "database", "chroma_db")
                    os.makedirs(chroma_path, exist_ok=True)
                    
                    logger.info(f"[Semantic Dedup] Initializing ChromaDB persistent client at {chroma_path}...")
                    _chroma_client = chromadb.PersistentClient(path=chroma_path)
                    
                    # Using cosine similarity space for vector distance matching
                    _collection = _chroma_client.get_or_create_collection(
                        name="scraped_deals_vectors",
                        metadata={"hnsw:space": "cosine"}
                    )
                except Exception as e:
                    logger.error(f"[Semantic Dedup] Failed to initialize ChromaDB collection: {e}")
                    raise
    return _collection

def add_deal_vector(product_id: str, title: str, price: int, timestamp: float = None):
    """
    Store the deal title embedding vector into ChromaDB for future duplicate queries.
    """
    if not title or not product_id:
        return

    if timestamp is None:
        timestamp = time.time()

    try:
        collection = get_chroma_collection()
        model = get_embedding_model()
        if not model:
            return
        
        # Compute embedding vector
        embeddings = list(model.embed([title]))
        if not embeddings:
            return
        vector = [float(val) for val in embeddings[0]]
        
        # Add to ChromaDB vector index
        collection.add(
            ids=[product_id],
            embeddings=[vector],
            documents=[title],
            metadatas=[{
                "price": int(price),
                "timestamp": float(timestamp)
            }]
        )
        logger.debug(f"[Semantic Dedup] Indexed deal vector for product ID {product_id} ('{title[:30]}')")
    except Exception as e:
        logger.error(f"[Semantic Dedup] Failed to index deal vector for {product_id}: {e}")

def find_semantic_duplicate(
    title: str,
    price: int,
    threshold: float = 0.85,
    time_window_hours: int = 24
) -> Optional[str]:
    """
    Generate the vector embedding of the input title and query ChromaDB for semantic duplicates.
    Filters by identical price and timestamp matching the sliding time window.
    Returns the duplicate product ID if found, otherwise None.
    """
    if not title:
        return None

    try:
        collection = get_chroma_collection()
        model = get_embedding_model()
        if not model:
            return None
        
        # Check if collection is empty
        if collection.count() == 0:
            return None

        # Compute query vector
        embeddings = list(model.embed([title]))
        if not embeddings:
            return None
        query_vector = [float(val) for val in embeddings[0]]

        # Search for closest matches using cosine distance
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=min(15, collection.count()),
            include=["documents", "metadatas", "distances"]
        )

        if not results or not results["ids"] or not results["ids"][0]:
            return None

        cutoff_time = time.time() - (time_window_hours * 3600)

        # Inspect results
        for idx in range(len(results["ids"][0])):
            matched_id = results["ids"][0][idx]
            metadata = results["metadatas"][0][idx]
            distance = results["distances"][0][idx]
            
            # Cosine similarity = 1 - cosine distance
            similarity = 1.0 - distance
            
            # Filter by matching price, time window, and similarity threshold
            if price is None or price == 0 or metadata.get("price") == price:
                if metadata.get("timestamp", 0) >= cutoff_time:
                    if similarity >= threshold:
                        logger.info(
                            f"[Semantic Dedup MATCH] Candidate '{title[:30]}' "
                            f"matched existing deal {matched_id} ('{results['documents'][0][idx][:30]}') "
                            f"Similarity: {similarity:.2f} (Threshold: {threshold})"
                        )
                        return matched_id
    except Exception as e:
        logger.error(f"[Semantic Dedup] Error querying semantic duplicate: {e}")
        
    return None
