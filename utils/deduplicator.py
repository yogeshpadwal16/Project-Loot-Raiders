# utils/deduplicator.py
import os
import logging
from fastembed import TextEmbedding
import chromadb

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SemanticDeduplicator")

# Instantiate FastEmbed model and Chroma client
# We use BAAI/bge-small-en-v1.5 as it is extremely light (~133MB), fast, and performs exceptionally well on CPUs.
_model = None
_collection = None

def _init_db():
    global _model, _collection
    if _model is not None and _collection is not None:
        return
        
    try:
        logger.info("Initializing FastEmbed text embedding model (BAAI/bge-small-en-v1.5)...")
        _model = TextEmbedding()
        
        logger.info("Initializing Chroma DB persistent client at database/chroma_db...")
        # Create persistent database folder
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "database", "chroma_db"))
        os.makedirs(db_path, exist_ok=True)
        
        chroma_client = chromadb.PersistentClient(path=db_path)
        _collection = chroma_client.get_or_create_collection(name="scraped_products", metadata={"hnsw:space": "cosine"})
        logger.info("Semantic Deduplicator engine loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Semantic Deduplicator: {e}")

def get_title_embedding(title: str) -> list:
    """
    Generates text embeddings list from FastEmbed generator.
    """
    _init_db()
    if not _model:
        return []
    try:
        embeddings = list(_model.embed([title]))
        if embeddings:
            return embeddings[0].tolist()
    except Exception as e:
        logger.error(f"Failed to generate embedding for '{title}': {e}")
    return []

def find_similar_product(title: str, distance_threshold: float = 0.15) -> str:
    """
    Queries ChromaDB to check if a semantically similar product already exists.
    Returns: The matched product ID string if distance is below threshold, else None.
    Notes: Cosine distance is used (0.0 means identical, 1.0 means opposite). 
           Threshold of 0.15 allows minor text/mismatch but catches duplicate deals.
    """
    _init_db()
    if not _collection:
        return None
        
    embedding = get_title_embedding(title)
    if not embedding:
        return None
        
    try:
        results = _collection.query(
            query_embeddings=[embedding],
            n_results=1
        )
        
        if results and results.get("distances") and len(results["distances"][0]) > 0:
            distance = results["distances"][0][0]
            matched_id = results["ids"][0][0]
            matched_doc = results["documents"][0][0]
            
            logger.info(f"Similarity search: Query='{title[:40]}' matched='{matched_doc[:40]}' (Distance={distance:.4f})")
            
            if distance <= distance_threshold:
                logger.info(f"Semantic match found! Match ID: {matched_id} for '{title[:45]}'")
                return matched_id
    except Exception as e:
        logger.error(f"ChromaDB query failure: {e}")
        
    return None

def add_product_to_vector_db(product_id: str, title: str):
    """
    Indexes a new product deal's title and ID inside local ChromaDB vector space.
    """
    _init_db()
    if not _collection:
        return False
        
    embedding = get_title_embedding(title)
    if not embedding:
        return False
        
    try:
        _collection.add(
            ids=[product_id],
            embeddings=[embedding],
            documents=[title]
        )
        logger.info(f"Indexed product '{title[:40]}' inside vector catalog (ID: {product_id}).")
        return True
    except Exception as e:
        logger.error(f"Failed to write to ChromaDB catalog: {e}")
    return False
