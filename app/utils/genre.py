from sentence_transformers import SentenceTransformer  # For generating embeddings
from scipy.spatial.distance import cosine  # For similarity calculation
from sqlalchemy.orm import Session  # For DB session
from app.db.models.unique_value import UniqueValue  # Model for unique fields
from typing import Optional  # For optional return type

# Load embedding model once
model = SentenceTransformer("all-MiniLM-L12-v2")


async def load_genre_embeddings_from_db(db: Session):
    # Fetch genres from DB and create embedding dict
    genre_row = db.query(UniqueValue).filter(UniqueValue.field == "genre").first()
    if not genre_row or not genre_row.unique_values:
        return {}

    genre_list = genre_row.unique_values
    return {genre: model.encode(genre) for genre in genre_list}


async def get_best_genre_match(input_genre: str, db: Session) -> Optional[str]:
    # Find best semantic match for input genre
    VALID_GENRE_EMBEDDINGS = await load_genre_embeddings_from_db(db)
    input_vec = model.encode(input_genre)

    best_match = None
    best_score = -1

    for genre, vec in VALID_GENRE_EMBEDDINGS.items():
        score = 1 - cosine(input_vec, vec)  # Cosine similarity
        if score > best_score:
            best_score = score
            best_match = genre

    return best_match if best_score >= 0.3 else None  # Return if similarity is good enough
